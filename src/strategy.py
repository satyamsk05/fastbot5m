"""
Streak Reversal Martingale Strategy
From tredebot: 3+ consecutive same-direction closes → bet OPPOSITE
Bet Sequence: 3 → 6 → 13 → 28 → 60 USDC
"""
import json
import os
import time
from utils.gsd_logger import get_gsd_logger
logger = get_gsd_logger("STRAT")
from typing import Optional, Dict, List

# ─── CONFIG ─────────────────────────────────────────────────────────────────
BET_SEQUENCE = [3, 6, 13, 28, 60]        # Martingale ladder (USDC)
STREAK_THRESHOLD = 3                       # Min consecutive candles to trigger
STATE_FILE = "data/martingale_state.json"
CANDLE_FILE = "data/candles.json"


# ─── MARTINGALE STATE ────────────────────────────────────────────────────────
class Martingale:
    """Per-coin Martingale step tracker with file persistence + file lock."""

    def __init__(self, state_file: str = STATE_FILE):
        self.state_file = state_file
        os.makedirs(os.path.dirname(state_file), exist_ok=True)

    # ── locking helpers ──────────────────────────────────────────────────────
    def _lock(self):
        lock_file = self.state_file + ".lock"
        
        # ── Cleanup stale lock if older than 10s ──
        if os.path.exists(lock_file):
            try:
                if time.time() - os.path.getmtime(lock_file) > 10:
                    os.remove(lock_file)
            except Exception: pass

        for _ in range(50):
            try:
                fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                return fd, lock_file
            except FileExistsError:
                time.sleep(0.05)
        return None, lock_file

    def _unlock(self, fd, lock_file):
        if fd is not None:
            os.close(fd)
            try:
                os.remove(lock_file)
            except Exception:
                pass

    def _load(self, coin: str) -> int:
        fd, lf = self._lock()
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, "r") as f:
                    return json.load(f).get(coin, 0)
            return 0
        except Exception:
            return 0
        finally:
            self._unlock(fd, lf)

    def _save(self, coin: str, step: int):
        fd, lf = self._lock()
        try:
            data = {}
            if os.path.exists(self.state_file):
                try:
                    with open(self.state_file, "r") as f:
                        data = json.load(f)
                except Exception:
                    pass
            data[coin] = step
            with open(self.state_file, "w") as f:
                json.dump(data, f)
        finally:
            self._unlock(fd, lf)

    # ── public API ───────────────────────────────────────────────────────────
    def get_bet(self, coin: str) -> float:
        step = self._load(coin)
        if step >= len(BET_SEQUENCE):
            step = 0
            self._save(coin, 0)
        return float(BET_SEQUENCE[step])

    def get_step(self, coin: str) -> int:
        return min(self._load(coin), len(BET_SEQUENCE) - 1)

    def win(self, coin: str):
        logger.info(f"[{coin}] Martingale WIN → reset to step 0")
        self._save(coin, 0)

    def lose(self, coin: str):
        step = self._load(coin)
        if step < len(BET_SEQUENCE) - 1:
            step += 1
            logger.info(f"[{coin}] Martingale LOSS → step {step}")
        else:
            logger.warning(f"[{coin}] Martingale MAX reached → reset to 0")
            step = 0
        self._save(coin, step)

    def reset_all(self):
        fd, lf = self._lock()
        try:
            with open(self.state_file, "w") as f:
                json.dump({}, f)
        finally:
            self._unlock(fd, lf)

    def get_all_steps(self) -> Dict[str, int]:
        """Return current step for every tracked coin."""
        fd, lf = self._lock()
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, "r") as f:
                    return json.load(f)
            return {}
        except Exception:
            return {}
        finally:
            self._unlock(fd, lf)


# ─── CANDLE STORE ────────────────────────────────────────────────────────────
class CandleStore:
    """
    Stores last-trade-price candle closes per coin/interval.
    One entry per market boundary (5-min slot).
    """

    def __init__(self, path: str = CANDLE_FILE):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._data: Dict[str, List[Dict]] = self._load()
        self._dirty = False

    def _load(self) -> Dict:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def flush(self):
        """Force flush to disk if there are unwritten changes."""
        if not self._dirty:
            return
        try:
            with open(self.path, "w") as f:
                json.dump(self._data, f)
            self._dirty = False
        except Exception as e:
            logger.error(f"[CANDLE] Flush error: {e}")

    def _flush(self):
        """Internal deprecated, use flush() for debounced disk I/O."""
        self._dirty = True

    def push(self, coin: str, ts: int, close_price: float):
        """Append a candle close. Keeps last 20 per coin."""
        key = coin.upper()
        if key not in self._data:
            self._data[key] = []
        # avoid duplicates
        if self._data[key] and self._data[key][-1]["ts"] == ts:
            return
        self._data[key].append({"ts": ts, "close": close_price})
        self._data[key] = self._data[key][-20:]
        self._flush()

    def get_closes(self, coin: str, n: int = 5) -> List[float]:
        """Return last n close prices for a coin."""
        key = coin.upper()
        entries = self._data.get(key, [])
        return [e["close"] for e in entries[-n:]]


# ─── SIGNAL DETECTION ────────────────────────────────────────────────────────
def check_streak_signal(closes: List[float]) -> Optional[str]:
    """
    Streak-reversal logic (from tredebot):
      - 3+ consecutive closes > 0.5  →  signal = "NO"  (bet DOWN/reverse)
      - 3+ consecutive closes < 0.5  →  signal = "YES" (bet UP/reverse)

    Returns "YES" | "NO" | None
    """
    if len(closes) < STREAK_THRESHOLD:
        return None
    last = closes[-STREAK_THRESHOLD:]
    if all(p > 0.5 for p in last):
        return "NO"
    if all(p < 0.5 for p in last):
        return "YES"
    return None


# ─── COMBINED SIGNAL WRAPPER ──────────────────────────────────────────────────
class StreakReversalStrategy:
    """
    Wraps signal detection + Martingale sizing.
    Called once per 5-min candle boundary per coin.
    """

    def __init__(self):
        self.martingale = Martingale()
        self.candles = CandleStore()

    def on_candle_close(self, coin: str, ts: int, close_price: float) -> Optional[Dict]:
        """
        Call at every 5-min boundary after price settles.
        Returns signal dict or None.

        Signal dict:
          direction : "YES" (UP) | "NO" (DOWN)
          amount    : USDC bet size
          step      : current martingale step (0-indexed)
          closes    : list of recent closes used
        """
        self.candles.push(coin, ts, close_price)
        closes = self.candles.get_closes(coin, n=STREAK_THRESHOLD + 1)
        signal = check_streak_signal(closes)
        if signal is None:
            return None

        amount = self.martingale.get_bet(coin)
        step   = self.martingale.get_step(coin)

        return {
            "direction": signal,   # "YES" = bet UP token, "NO" = bet DOWN token
            "amount":    amount,
            "step":      step,
            "closes":    closes,
            "coin":      coin.upper(),
            "ts":        ts,
            "ts_sig":    time.time(), # Added: creation timestamp for latency tracking
        }

    def on_result(self, coin: str, won: bool):
        """Update Martingale after trade resolution."""
        if won:
            self.martingale.win(coin)
        else:
            self.martingale.lose(coin)
