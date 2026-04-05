"""
Telegram Bot - Minimalist UI (Style 2)
══════════════════════════════════════════════════════
Commands:
  🖥 Live      → /live (with inline refresh)
  🏦 Wallet    → /balance
  📦 Open      → /position
  📜 Log       → /history
  📈 Trend     → Visual Streak Analysis (Circles)
  📊 PnL       → /daily_pnl
  🩺 System    → /health
  ⚡ Quick Bet  → /manual_bet (Interactive Inline Flow)
  ⏹ Pause     → /stop (toggle)
══════════════════════════════════════════════════════
"""
import os
from utils.gsd_logger import get_gsd_logger
logger = get_gsd_logger("TG_BOT")
import asyncio
import threading
import time
import random
import string
from datetime import datetime
from typing import Optional, Callable, Dict

try:
    from telegram import Bot, Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
    from telegram.ext import (Application, CommandHandler, MessageHandler,
                               CallbackQueryHandler, ContextTypes, filters)
    TELEGRAM_OK = True
except ImportError:
    TELEGRAM_OK = False

import history_manager as hm

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

# ── format helpers ─────────────────────────────────────────────────────────────
def _box(title: str, lines: list) -> str:
    """OG-style ━━━━━━━━━━━━━━━━━━━━ box."""
    sep = "━━━━━━━━━━━━━━━━━━━━"
    body = "\n".join(lines)
    return f"*{title}*\n{sep}\n{body}\n{sep}"

# ══════════════════════════════════════════════════════════════════════════════
# BOT CLASS
# ══════════════════════════════════════════════════════════════════════════════
class TelegramBot:
    """Full async Telegram bot. Option 2 Minimalist style."""
    def __init__(self):
        self._loop:   Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._app     = None
        self._running = False
        
        # Unique session ID for each start
        self.session_id = "#" + "".join(random.choices(string.ascii_uppercase + string.digits, k=5))

        # Callbacks set by main.py
        self.get_live_state: Optional[Callable] = None    # () → {coin: {up_ask, down_ask, seconds_till_end}}
        self.get_balance:    Optional[Callable] = None    # () → float
        self.get_real_bal:   Optional[Callable] = None    # () → float (on-chain balance)
        self.get_in_bets:    Optional[Callable] = None    # () → float  (USDC locked in open bets)
        self.on_stop:        Optional[Callable] = None    # () → None   (pause trading)
        self.on_manual_bet:  Optional[Callable] = None   # (coin, dir, amount) → str  (result message)
        self.is_paused:      bool = False
        self.active_coins:   list = ["BTC", "ETH", "SOL", "XRP"]
        self.get_health:     Optional[Callable] = None    # () → dict

        if TELEGRAM_OK and BOT_TOKEN and CHAT_ID:
            self._start_thread()
        else:
            logger.warning("[TG] Telegram not configured properly.")

    def _start_thread(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, daemon=True, name="telegram")
        self._thread.start()

    def _run(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._run_app())

    async def _run_app(self):
        self._app = Application.builder().token(BOT_TOKEN).build()
        app = self._app

        # Handlers
        app.add_handler(CommandHandler("start",   self._cmd_start))
        app.add_handler(CommandHandler("menu",    self._cmd_start))
        app.add_handler(CommandHandler("history", self._cmd_history))
        app.add_handler(CommandHandler("live",    self._cmd_live))
        app.add_handler(CommandHandler("stop",    self._cmd_stop))
        app.add_handler(CommandHandler("balance", self._cmd_balance))
        app.add_handler(CommandHandler("position", self._cmd_position))
        app.add_handler(CommandHandler("daily_pnl", self._cmd_daily_pnl))
        app.add_handler(CommandHandler("health",  self._cmd_health))
        app.add_handler(CommandHandler("trend",   self._cmd_trend))
        app.add_handler(CallbackQueryHandler(self._on_callback))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message))

        self._running = True
        logger.info(f"[TG] Initializing Application with token: {BOT_TOKEN[:5]}...{BOT_TOKEN[-5:]}")
        await app.initialize()
        logger.info("[TG] Starting Application...")
        await app.start()
        logger.info("[TG] Starting Polling...")
        await app.updater.start_polling(drop_pending_updates=True)
        logger.info("[TG] Bot is now ONLINE and polling.")

        # Remove hamburger menu
        try: 
            await app.bot.delete_my_commands()
            logger.info("[TG] Commands menu cleared.")
        except Exception as e:
            logger.warning(f"[TG] Could not clear commands: {e}")

        # Keyboard is active via reply_markup on first command or persistent menu
        pass

        while self._running:
            await asyncio.sleep(1)

        await app.updater.stop()
        await app.stop()
        await app.shutdown()

    def send(self, text: str, parse_mode: str = "Markdown"):
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._send_async(text, parse_mode), self._loop)

    async def _send_async(self, text: str, parse_mode: str):
        try:
            await self._app.bot.send_message(chat_id=CHAT_ID, text=text, parse_mode=parse_mode)
        except: pass

    def _get_kb(self):
        """Minimalist Option 2 Keyboard."""
        from telegram import ReplyKeyboardMarkup, KeyboardButton
        stop_label = "▶ Resume" if self.is_paused else "■ Pause"
        return ReplyKeyboardMarkup(
            [
                [KeyboardButton("🖥 Live"),    KeyboardButton("🏦 Wallet"), KeyboardButton("📦 Open")],
                [KeyboardButton("📜 Log"),     KeyboardButton("📈 Trend"),  KeyboardButton("🩺 System")],
                [KeyboardButton("⚡ Quick Bet"), KeyboardButton("📊 PnL"),    KeyboardButton(stop_label)],
            ],
            resize_keyboard=True,
            is_persistent=False,
            one_time_keyboard=False
        )

    # ── Command Handlers ───────────────────────────────────────────────────

    async def _cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("👋 *Bot Started!* Minimalist dashboard active.", 
                                        parse_mode="Markdown", reply_markup=self._get_kb())

    async def _cmd_history(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        bets = hm.get_bet_history(n=10)
        if not bets:
            await update.message.reply_text("📊 *History is empty.*", parse_mode="Markdown", reply_markup=self._get_kb())
            return
        lines = []
        for b in reversed(bets):
            res = b.get("result", "OPEN")
            pnl = b.get("pnl")
            if pnl is None: pnl = 0.0
            
            coin = b.get("coin", "???")
            amt = b.get("amount", 0.0)
            icon = "🟢" if res == "WIN" else "🔴" if res == "LOSS" else "⏳"
            sign = "+" if pnl > 0 else ""
            res_str = f"{sign}${pnl:.2f}" if res != "OPEN" else "PENDING"
            lines.append(f"{icon} *{coin}* - *${amt:.0f}* ({res_str})")
        await update.message.reply_text(_box("📜 RECENT LOGS", lines), parse_mode="Markdown", reply_markup=self._get_kb())

    async def _cmd_live(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self.get_live_state:
            await update.message.reply_text("Live data unavailable.", reply_markup=self._get_kb())
            return
        states = self.get_live_state()
        lines = []
        rem_sec = 0
        for coin in self.active_coins:
            st = states.get(coin, {})
            up = st.get("up_ask", 0.0)
            dn = st.get("down_ask", 0.0)
            rem_sec = st.get("seconds_till_end", 300)
            
            lines.append(f"🌟 *{coin}*")
            lines.append(f"  🟢 *YES:* *${up:.2f}*  |  🔴 *NO:* *${dn:.2f}*")
            lines.append("──────────────────────────")
        
        # Format timer
        m, s = divmod(rem_sec, 60)
        timer_str = f"⏰ *{m:02d}:{s:02d}*"
        
        header = "📈 LIVE PRICES"
        body = "\n".join(lines[:-1]) # remove last separator
        text = f"*{header}*\n──────────────────────────\n{body}\n{timer_str}"
        
        kb = [[InlineKeyboardButton("🔄 Refresh", callback_data="refresh_live")]]
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        else:
            await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

    async def _cmd_stop(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        self.is_paused = not self.is_paused
        if self.on_stop: self.on_stop(self.is_paused)
        status = "⏹ *PAUSED* — news bets disabled" if self.is_paused else "▶ *RESUMED* — active"
        await update.message.reply_text(f"*{status}*", parse_mode="Markdown", reply_markup=self._get_kb())

    async def _cmd_balance(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        avail = self.get_balance() if self.get_balance else 0.0
        real  = self.get_real_bal() if self.get_real_bal else 0.0
        in_bets = self.get_in_bets() if self.get_in_bets else 0.0
        await update.message.reply_text(
            _box("🏦 WALLET STATUS", [
                f"*Virtual Bal* → *${avail:.2f}*",
                f"*In Bets*     → *${in_bets:.2f}*",
                f"*Real Chain*  → *${real:.2f}*",
            ]),
            parse_mode="Markdown", reply_markup=self._get_kb()
        )

    async def _cmd_position(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        positions = hm.get_open_positions()
        if not positions:
            await update.message.reply_text("📌 *No open positions.*", parse_mode="Markdown", reply_markup=self._get_kb())
            return
        lines = []
        for coin, pos in positions.items():
            arrow = "UP" if pos["direction"] == "YES" else "DOWN"
            lines.append(f"📦 *{coin}* → *${pos['amount']:.0f}* @ *{pos['price']:.3f}* (*{arrow}*)")
        await update.message.reply_text(_box("📦 OPEN POSITIONS", lines), parse_mode="Markdown", reply_markup=self._get_kb())

    async def _cmd_daily_pnl(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        summary = hm.get_pnl_summary(days=7)
        bold_summary = summary
        await update.message.reply_text(f"*📅 Daily PNL (7 days)*\n\n{bold_summary}", 
                                        parse_mode="Markdown", reply_markup=self._get_kb())

    async def _cmd_health(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self.get_health:
            await update.message.reply_text("Health unavailable.", reply_markup=self._get_kb())
            return
        h = self.get_health()
        lines = [
            f"*OVERALL*  → *{'🟢 OK' if h.get('ok') else '🔴 ERROR'}*",
            f"*UPTIME*   → *{h.get('uptime', '0m')}*",
            f"*POL WAL*  → *{h.get('pol_balance', 0.0):.2f} POL*",
            f"*LOG SZ*   → *{h.get('log_size', '0 KB')}*",
        ]
        await update.message.reply_text(_box("🩺 SYSTEM HEALTH", lines), parse_mode="Markdown", reply_markup=self._get_kb())

    async def _cmd_trend(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Visual Streak Analysis using red/green circles."""
        lines = []
        for coin in self.active_coins:
            candles = hm.get_candle_history(coin, n=10)
            # Create circles string
            circles = []
            ups = 0
            downs = 0
            # Pad with white circles if less than 10
            pad_count = 10 - len(candles)
            for _ in range(pad_count): circles.append("⚪")
            
            for c in candles:
                if c["dir"] == "UP":
                    circles.append("🟢")
                    ups += 1
                else:
                    circles.append("🔴")
                    downs += 1
            
            circles_str = "".join(circles)
            lines.append(f"*{coin:<4}* {circles_str} → *UP:{ups}* | *DN:{downs}*")
        
        header = "📊 TREND DATA"
        sep = "──────────────────────────"
        body = "\n".join(lines)
        footer = "Trend → Streak Analysis Active"
        text = f"*{header}*\n{sep}\n{body}\n\n{footer}"
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=self._get_kb())

    async def _on_message(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        text = (update.message.text or "").strip()
        btn_map = {
            "🖥 Live":    self._cmd_live,
            "🏦 Wallet":  self._cmd_balance,
            "📦 Open":    self._cmd_position,
            "📜 Log":     self._cmd_history,
            "📈 Trend":   self._cmd_trend,
            "📊 PnL":     self._cmd_daily_pnl,
            "🩺 System":  self._cmd_health,
            "⚡ Quick Bet": self._cmd_manual_bet,
            "■ Pause":   self._cmd_stop,
            "▶ Resume":  self._cmd_stop
        }
        if text in btn_map:
            await btn_map[text](update, ctx)

    # ── Interactive Manual Bet Flow ───────────────────────────────────────

    async def _cmd_manual_bet(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Step 1: Select Coin."""
        kb = [
            [InlineKeyboardButton(c, callback_data=f"mb:{c}") for c in self.active_coins]
        ]
        await update.message.reply_text(
            "🎯 *Select Coin to Trade*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    async def _on_callback(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data = query.data.split(":")

        if data[0] == "refresh_live":
            await self._cmd_live(update, ctx)
            return

        if data[0] != "mb":
            return

        # mb:COIN
        if len(data) == 2:
            coin = data[1]
            kb = [
                [
                    InlineKeyboardButton("UP 🟢 (YES)", callback_data=f"mb:{coin}:YES"),
                    InlineKeyboardButton("DOWN 🔴 (NO)", callback_data=f"mb:{coin}:NO")
                ],
                [InlineKeyboardButton("❌ Cancel", callback_data="mb:cancel")]
            ]
            await query.edit_message_text(
                f"🔸 *Coin:* *{coin}*\n\n📈 *Select Direction*",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(kb)
            )

        # mb:COIN:DIR
        elif len(data) == 3:
            coin, direction = data[1], data[2]
            amounts = [1, 2, 3, 5]
            kb = [
                [InlineKeyboardButton(f"${a}", callback_data=f"mb:{coin}:{direction}:{a}") for a in amounts],
                [InlineKeyboardButton("❌ Cancel", callback_data="mb:cancel")]
            ]
            arrow = "UP 🟢" if direction == "YES" else "DOWN 🔴"
            await query.edit_message_text(
                f"🔸 *Coin:* *{coin}*\n🔸 *Dir:* *{arrow}*\n\n💰 *Select Amount*",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(kb)
            )

        # mb:COIN:DIR:AMT
        elif len(data) == 4:
            coin, direction, amount = data[1], data[2], float(data[3])
            arrow = "UP 🟢" if direction == "YES" else "DOWN 🔴"
            
            await query.edit_message_text(f"⏳ *Executing {coin} {arrow} trade for ${amount:.0f}...*", parse_mode="Markdown")
            
            if self.on_manual_bet:
                res = self.on_manual_bet(coin, direction, amount)
                await query.edit_message_text(res, parse_mode="Markdown")
            else:
                await query.edit_message_text("❌ *Error: Manual bet callback not wired.*")

        elif data[1] == "cancel":
            await query.edit_message_text("❌ *Trade Canceled.*", parse_mode="Markdown")

class TelegramNotifier:
    """Standard notifier for alerts."""
    def __init__(self, bot: "TelegramBot"):
        self._bot = bot

    def send(self, text: str):
        self._bot.send(text)

    def notify_startup(self, coins: list, dry_run: bool):
        now = datetime.now().strftime("%H:%M:%S")
        sid = self._bot.session_id
        msg = (
            f"⏱ *Started:* *{now} IST*\n"
            f"🔢 *Session:* *{sid}*"
        )
        self.send(msg)

    def notify_trade_placed(self, coin: str, direction: str, amount: float, price: float, order_type: str, step: int):
        arrow = "UP" if direction == "YES" else "DOWN"
        self.send(_box(f"✅ TRADE PLACED: {coin}", [
            f"*Side:* *{arrow}*",
            f"*Size:* *${amount:.0f}*",
            f"*Price:* *{price:.3f}*"
        ]))

    def notify_result(self, coin: str, direction: str, amount: float, won: bool, payout: float, next_step: int):
        status = "✅ WIN" if won else "❌ LOSS"
        pnl = payout - amount if won else -amount
        self.send(_box(f"📊 RESULT: {coin}", [
            f"*State:* *{status}*",
            f"*PnL:*   *{'+' if pnl>=0 else ''}${pnl:.2f}*"
        ]))

    def notify_insufficient_funds(self, coin: str, balance: float, need: float):
        """Send a low funds alert."""
        self.send(_box(f"⚠️ LOW FUNDS: {coin}", [
            f"*Available:* *${balance:.2f}*",
            f"*Needed:*    *${need:.2f}*",
            f"*Advice:*    Add more USDC to your wallet."
        ]))

    def send_market_closed(self, coin: str, trade: Dict, session_stats: Dict, portfolio_stats: Dict):
        """Send a formatted notification for a closed market (used by redeem collector)."""
        pnl = trade.get("pnl", 0.0)
        roi = trade.get("roi_pct", 0.0)
        status = "✅ WIN" if pnl >= 0 else "❌ LOSS"
        
        self.send(_box(f"📊 SETTLED: {coin}", [
            f"*Status:*   *{status}*",
            f"*PnL:*      *{'+' if pnl>=0 else ''}${pnl:.2f}*",
            f"*ROI:*      *{roi:+.1f}%*",
            f"*Portfolio:* *{portfolio_stats.get('total_pnl', 0.0):+.2f}*"
        ]))

    def notify_error(self, title: str, details: str):
        """Send a critical error alert."""
        self.send(_box(f"🚨 ALERT: {title}", [
            f"*Details:* *{details}*",
            f"*Time:*    *{datetime.now().strftime('%H:%M:%S')}*"
        ]))

# Singleton getters
_bot_instance: Optional[TelegramBot] = None
def get_bot() -> TelegramBot:
    global _bot_instance
    if _bot_instance is None: _bot_instance = TelegramBot()
    return _bot_instance
def get_notifier() -> TelegramNotifier:
    return TelegramNotifier(get_bot())
