"""
Telegram Notifier
Handles all Telegram messages: trade alerts, status, commands.
Based on 4coinsbot's telegram_notifier.py structure.
"""
import os
from utils.gsd_logger import get_gsd_logger
logger = get_gsd_logger("TG_NOTIFY")
import asyncio
import threading
from typing import Optional

try:
    from telegram import Bot, Update
    from telegram.ext import Application, CommandHandler, ContextTypes
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

BOT_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID    = os.getenv("TELEGRAM_CHAT_ID", "")


def _fmt_box(title: str, lines: list) -> str:
    """Standard Telegram box format (Og's style)."""
    body = "\n".join(f"» {l}" for l in lines)
    return f"╔══ {title} ══╗\n{body}\n╚{'═'*(len(title)+6)}╝"


class TelegramNotifier:
    def __init__(self):
        self.bot: Optional[object] = None
        self.chat_id = CHAT_ID
        self._loop = None
        self._thread = None
        self._app = None
        self._command_callbacks = {}  # name → async fn

        if TELEGRAM_AVAILABLE and BOT_TOKEN and CHAT_ID:
            self._start_thread()
        else:
            logger.warning("[TG] Telegram not configured – running silently")

    # ── background thread ────────────────────────────────────────────────────
    def _start_thread(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    # ── send helpers ─────────────────────────────────────────────────────────
    def send(self, text: str, parse_mode: str = "Markdown"):
        if not TELEGRAM_AVAILABLE or not BOT_TOKEN or not CHAT_ID:
            logger.info(f"[TG] {text}")
            return
        try:
            async def _do():
                bot = Bot(token=BOT_TOKEN)
                await bot.send_message(chat_id=CHAT_ID, text=text,
                                       parse_mode=parse_mode)
            if self._loop and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(_do(), self._loop)
        except Exception as e:
            logger.error(f"[TG] send error: {e}")

    # ── trade notifications ───────────────────────────────────────────────────
    def notify_signal(self, coin: str, direction: str, amount: float,
                      step: int, closes: list):
        d_emoji = "🟢" if direction == "YES" else "🔴"
        arrow   = "↑ UP" if direction == "YES" else "↓ DOWN"
        trend   = "↑↑↑" if direction == "NO" else "↓↓↓"  # streak direction
        msg = _fmt_box(
            f"{d_emoji} SIGNAL {coin}",
            [
                f"Side  : {arrow}",
                f"Bet   : ${amount:.0f} USDC",
                f"Step  : L{step+1} ({'/'.join(str(b) for b in [3,6,13,28,60])})",
                f"Streak: {trend}",
                f"Closes: {[f'{c:.2f}' for c in closes[-3:]]}",
            ]
        )
        self.send(msg)

    def notify_trade_placed(self, coin: str, direction: str, amount: float,
                            price: float, order_type: str, step: int):
        arrow = "↑ YES" if direction == "YES" else "↓ NO"
        msg = _fmt_box(
            f"🎯 PLACED {coin}",
            [
                f"Side  : {arrow}",
                f"Bet   : ${amount:.0f}",
                f"Price : {price:.3f}",
                f"Type  : {order_type}",
                f"Level : L{step+1}",
            ]
        )
        self.send(msg)

    def notify_result(self, coin: str, direction: str, amount: float,
                      won: bool, payout: float, next_step: int):
        emoji = "✅ WON" if won else "❌ LOST"
        pnl   = payout - amount if won else -amount
        sign  = "+" if pnl >= 0 else ""
        msg = _fmt_box(
            f"{emoji} {coin}",
            [
                f"Side  : {'↑ YES' if direction=='YES' else '↓ NO'}",
                f"PnL   : {sign}${pnl:.2f}",
                f"Next  : {'Reset L1' if won else f'Recovery L{next_step+1}'}",
            ]
        )
        self.send(msg)

    def notify_insufficient_funds(self, coin: str, balance: float, need: float):
        self.send(_fmt_box(
            "⚠️ LOW FUNDS",
            [f"Coin   : {coin}",
             f"Wallet : ${balance:.2f}",
             f"Need   : ${need:.2f}",
             f"Action : Signal skipped"]
        ))

    def notify_startup(self, coins: list, dry_run: bool):
        mode = "~ DRY RUN ~" if dry_run else "LIVE"
        self.send(_fmt_box(
            "🚀 BOT STARTED",
            [f"Mode   : {mode}",
             f"Coins  : {', '.join(coins)}",
             f"Ladder : 3→6→13→28→60 USDC",
             f"Signal : 3-streak reversal"]
        ))

    def notify_error(self, context: str, error: str):
        self.send(f"🚨 *ERROR* `{context}`\n```{str(error)[:200]}```")


# ── singleton ─────────────────────────────────────────────────────────────────
_notifier: Optional[TelegramNotifier] = None

def get_notifier() -> TelegramNotifier:
    global _notifier
    if _notifier is None:
        _notifier = TelegramNotifier()
    return _notifier
