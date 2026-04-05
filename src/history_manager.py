"""
History Manager
══════════════════════════════════════════════════════
Manages all persistent state files:
  history/bet_history.json   → every bet placed (result, PnL)
  history/candle_history.json→ 7-day 5-min candle closes per coin
  history/open_positions.json→ currently open bets
  history/daily_pnl.json     → date-wise P&L summary
══════════════════════════════════════════════════════
"""
import json
import os
import time
import threading
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
from utils.gsd_logger import get_gsd_logger
logger = get_gsd_logger("HIST")

HISTORY_DIR  = os.path.join(os.path.dirname(__file__), "..", "history")
BET_FILE     = os.path.join(HISTORY_DIR, "bet_history.json")
CANDLE_FILE  = os.path.join(HISTORY_DIR, "candle_history.json")
POSITION_FILE= os.path.join(HISTORY_DIR, "open_positions.json")
DAILY_PNL_FILE = os.path.join(HISTORY_DIR, "daily_pnl.json")
WARMUP_FILE    = os.path.join(HISTORY_DIR, "warmup.json")

MAX_CANDLE_DAYS = 7          # 7-day candle retention
CANDLES_PER_DAY = 288         # 5-min candles per day (24h * 12)
MAX_CANDLES = MAX_CANDLE_DAYS * CANDLES_PER_DAY  # 2016

_lock = threading.Lock()

os.makedirs(HISTORY_DIR, exist_ok=True)


# ── helpers ────────────────────────────────────────────────────────────────────
def _read(path: str) -> dict | list:
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {} if path.endswith("history.json") or "pnl" in path else []


def _write(path: str, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _today_str() -> str:
    return date.today().strftime("%d %b")   # "26 Mar"


# ══════════════════════════════════════════════════════════════════════════════
# RESET — called on every bot restart
# ══════════════════════════════════════════════════════════════════════════════
def reset_on_startup():
    """
    Reset open_positions and candle_history on every bot start.
    bet_history and daily_pnl are KEPT across restarts.
    """
    with _lock:
        _write(POSITION_FILE, {})
        _write(CANDLE_FILE,   {})
        # WARMUP_FILE is kept to allow instant resumes
    logger.info("[HISTORY] Position and Candle history reset on startup (Warmup & Bets preserved).")


# ══════════════════════════════════════════════════════════════════════════════
# BET HISTORY
# ══════════════════════════════════════════════════════════════════════════════
def log_bet_placed(coin: str, direction: str, amount: float,
                   price: float, order_type: str, step: int,
                   market_ts: int, token_id: str, is_dry_run: bool = False):
    """Record a bet placement."""
    with _lock:
        data = _read(BET_FILE)
        if not isinstance(data, list):
            data = []
        data.append({
            "id":         len(data) + 1,
            "coin":       coin,
            "direction":  direction,          # YES / NO
            "amount":     amount,
            "price":      price,
            "order_type": order_type,
            "step":       step,
            "market_ts":  market_ts,
            "token_id":   token_id,
            "placed_at":  int(time.time()),
            "dry_run":    is_dry_run,         # Added: distinguish simulation
            "result":     None,               # WIN / LOSS — filled on resolution
            "pnl":        None,
            "fee":        0.0,                # Added: 0.24% estimation
        })
        _write(BET_FILE, data)


def log_bet_result(coin: str, market_ts: int, won: bool, pnl: float, fee: float = 0.0):
    """Update result of a bet after resolution."""
    with _lock:
        data = _read(BET_FILE)
        if not isinstance(data, list):
            return
        for bet in reversed(data):
            if bet["coin"] == coin and bet["market_ts"] == market_ts and bet["result"] is None:
                bet["result"] = "WIN" if won else "LOSS"
                bet["pnl"]    = round(pnl, 4)
                bet["fee"]    = round(fee, 4)
                bet["resolved_at"] = int(time.time())
                break
        _write(BET_FILE, data)

def get_bet_history(n: Optional[int] = None) -> List[Dict]:
    """Returns history, optionally truncated to the last n items."""
    with _lock:
        data = _read(BET_FILE)
        if not isinstance(data, list):
            return []
        return data[-n:] if n is not None else data


# ══════════════════════════════════════════════════════════════════════════════
# CANDLE HISTORY  (7-day rolling)
# ══════════════════════════════════════════════════════════════════════════════
def push_candle(coin: str, ts: int, close_price: float):
    """Store a candle close. Keeps last MAX_CANDLES per coin."""
    with _lock:
        data = _read(CANDLE_FILE)
        if not isinstance(data, dict):
            data = {}
        key = coin.upper()
        if key not in data:
            data[key] = []

        # Deduplicate by ts
        if data[key] and data[key][-1]["ts"] == ts:
            return

        data[key].append({
            "ts":    ts,
            "close": close_price,
            "dir":   "UP" if close_price > 0.5 else "DOWN",
        })
        # Keep only 7 days
        data[key] = data[key][-MAX_CANDLES:]
        _write(CANDLE_FILE, data)


def get_candle_history(coin: str, n: int = MAX_CANDLES) -> List[Dict]:
    with _lock:
        data = _read(CANDLE_FILE)
        if not isinstance(data, dict):
            return []
        return data.get(coin.upper(), [])[-n:]



def get_candle_closes(coin: str, n: int = 5) -> List[float]:
    return [c["close"] for c in get_candle_history(coin, n)]


def get_7day_trend_bar(coin: str) -> str:
    """
    Returns a visual trend bar for /history command.
    Each candle = 🟩 (UP) or 🟥 (DOWN). Last 48 candles (12h) shown.
    """
    candles = get_candle_history(coin, n=48)
    if not candles:
        return "(no data)"
    bar = "".join("🟢" if c["dir"] == "UP" else "🔴" for c in candles)
    # Add summary stats
    ups   = sum(1 for c in candles if c["dir"] == "UP")
    downs = len(candles) - ups
    return f"{bar}\n  🟢 UP: {ups} | 🔴 DOWN: {downs} | Last 48 candles"


# ══════════════════════════════════════════════════════════════════════════════
# OPEN POSITIONS
# ══════════════════════════════════════════════════════════════════════════════
def open_position(coin: str, direction: str, amount: float,
                  price: float, market_ts: int, token_id: str):
    """Add an open position."""
    with _lock:
        data = _read(POSITION_FILE)
        if not isinstance(data, dict):
            data = {}
        data[coin.upper()] = {
            "direction":  direction,
            "amount":     amount,
            "price":      price,
            "market_ts":  market_ts,
            "token_id":   token_id,
            "opened_at":  int(time.time()),
        }
        _write(POSITION_FILE, data)


def close_position(coin: str):
    """Remove a position after resolution."""
    with _lock:
        data = _read(POSITION_FILE)
        if isinstance(data, dict) and coin.upper() in data:
            del data[coin.upper()]
            _write(POSITION_FILE, data)


def get_open_positions() -> Dict:
    with _lock:
        data = _read(POSITION_FILE)
        return data if isinstance(data, dict) else {}


def get_warmup_state() -> Dict[str, int]:
    with _lock:
        data = _read(WARMUP_FILE)
        return data if isinstance(data, dict) else {}

def save_warmup_state(states: Dict[str, int]):
    with _lock:
        _write(WARMUP_FILE, states)


# ══════════════════════════════════════════════════════════════════════════════
# DAILY PNL
# ══════════════════════════════════════════════════════════════════════════════
def record_pnl(pnl: float, is_dry_run: bool = False):
    """Add pnl to today's total."""
    with _lock:
        data = _read(DAILY_PNL_FILE)
        if not isinstance(data, dict):
            data = {}
        today = _today_str()
        
        # Support new dictionary format for fee tracking
        day_data = data.get(today, {"pnl": 0.0, "fee": 0.0, "v_pnl": 0.0, "v_fee": 0.0})
        if isinstance(day_data, (int, float)):
            day_data = {"pnl": float(day_data), "fee": 0.0, "v_pnl": 0.0, "v_fee": 0.0}
            
        key = "v_pnl" if is_dry_run else "pnl"
        day_data[key] = round(day_data[key] + pnl, 4)
        data[today] = day_data
        _write(DAILY_PNL_FILE, data)

def record_fee(fee: float, is_dry_run: bool = False):
    """Add fee to today's total."""
    with _lock:
        data = _read(DAILY_PNL_FILE)
        if not isinstance(data, dict):
            data = {}
        today = _today_str()
        
        day_data = data.get(today, {"pnl": 0.0, "fee": 0.0, "v_pnl": 0.0, "v_fee": 0.0})
        if isinstance(day_data, (int, float)):
            day_data = {"pnl": float(day_data), "fee": 0.0, "v_pnl": 0.0, "v_fee": 0.0}
            
        key = "v_fee" if is_dry_run else "fee"
        day_data[key] = round(day_data[key] + fee, 4)
        data[today] = day_data
        _write(DAILY_PNL_FILE, data)


def get_daily_pnl() -> Dict[str, float]:
    with _lock:
        data = _read(DAILY_PNL_FILE)
        return data if isinstance(data, dict) else {}

def get_total_pnl(is_dry_run: bool = False) -> float:
    data = get_daily_pnl()
    total = 0.0
    key = "v_pnl" if is_dry_run else "pnl"
    for val in data.values():
        total += val.get(key, 0.0) if isinstance(val, dict) else (float(val) if not is_dry_run else 0.0)
    return round(total, 4)

def get_total_fees(is_dry_run: bool = False) -> float:
    data = get_daily_pnl()
    total = 0.0
    key = "v_fee" if is_dry_run else "fee"
    for val in data.values():
        total += val.get(key, 0.0) if isinstance(val, dict) else 0.0
    return round(total, 4)


def get_pnl_summary(days: int = 7) -> str:
    """Returns formatted PNL for Telegram /daily_pnl command."""
    data = get_daily_pnl()
    lines = []
    for i in range(days):
        day = (datetime.now() - timedelta(days=i)).strftime("%d %b")
        iso = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        
        day_data = data.get(iso, {"pnl": 0.0, "fee": 0.0, "v_pnl": 0.0, "v_fee": 0.0})
        if isinstance(day_data, (int, float)):
            day_data = {"pnl": float(day_data), "fee": 0.0, "v_pnl": 0.0, "v_fee": 0.0}
            
        pnl = day_data.get("pnl", 0.0)
        fee = day_data.get("fee", 0.0)
        v_pnl = day_data.get("v_pnl", 0.0)
        
        icon = "🟢" if pnl >= 0 else "🔴"
        v_icon = "🧪" # Virtual
        
        line = f"*{icon} {day}:* *${pnl:+.2f}* (Fee: *${fee:.2f}*)"
        if v_pnl != 0:
            line += f"\n   {v_icon} Sim: *${v_pnl:+.2f}*"
            
        lines.append(line)
        
    total_real = get_total_pnl(is_dry_run=False)
    total_virt = get_total_pnl(is_dry_run=True)
    
    footer = f"\n💰 Real Total: *${total_real:+.2f}*"
    if total_virt != 0:
        footer += f"\n🧪 Sim Total:  *${total_virt:+.2f}*"
    
    return "\n".join(lines) + footer
