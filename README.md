# 💎 FASTBOT: Polymarket Streak-Reversal Suite v3.0

[![Status](https://img.shields.io/badge/Status-Production--Ready-brightgreen)](https://github.com/satyamsk05/Fastbot)
[![Version](https://img.shields.io/badge/Version-3.0.0-blue)](https://github.com/satyamsk05/Fastbot)
[![Strategy](https://img.shields.io/badge/Strategy-5m--Martingale--Reversal-orange)](https://github.com/satyamsk05/Fastbot)

A premium, high-performance trading suite for Polymarket. **Fastbot** combines ultra-low latency infrastructure with a battle-tested **5-minute streak-reversal strategy** and an optimized **Martingale execution engine**.

---

## ⚡ A2Z Technical Strategy

### 📊 1. The 5-Minute Reversal Engine
Fastbot monitors 5-minute price boundaries on **BTC, ETH, SOL, and XRP**.
- **Signal Logic**: Detects a "streak" of **3+ consecutive same-direction closes** (e.g., three 🟢 candles or three 🔴 candles).
- **Execution**: At the 5m boundary (plus a 5s settlement buffer), the bot places a **Reversal Bet** (e.g., if 3 UP candles, it bets DOWN).
- **Why 5m?**: This interval provides high-frequency trading opportunities with consistent trend reversals in volatile markets.

### 🪜 2. Martingale Recovery Ladder
If a signal results in a loss, Fastbot automatically scales the position to recover:
- **Ladder**: `$3 → $6 → $13 → $28 → $60 USDC`
- **Logic**: Resets to `$3` immediately after a WIN or reaching the Max Level cap to protect capital.
- **Persistence**: Martingale state is saved to `data/martingale_state.json` to survive bot restarts.

### 🎯 3. Optimized Pricing Brackets
Fastbot uses dual-layer pricing optimized for 5m market spreads:
- **L1 (Step 0 - Entry)**: Market-like (FOK) order within a **0.40 - 0.60 USDC** bracket. This allows for entry in higher volatility.
- **L2-L5 (Martingale Recovery)**: Limit (GTC) orders locked within a **0.47 - 0.54 USDC** bracket.
- **Targeted Buying**: By capping recovery orders at `0.54`, the bot waits for the market to move to an optimal price, effectively **buying at the lowest possible rates** during recovery phases.

---

## 🚀 Key Features

### 🏁 Zero-Latency Terminal Dashboard
- **4Hz Refresh Rate**: UI updates every **0.25 seconds (400ms)** for a smooth, "instant-action" feel.
- **Compact Layout**: Optimized to **120-character width** for standard terminal windows.
- **Background Balance Sync**: Wallet balances (Native USDC/USDC.e) are synced in a separate thread, ensuring the UI **never freezes** during network requests.

### 📱 Interactive Telegram Hub (3x3 Menu)
- **Live State**: Quick view of active prices and market timers.
- **Manual Trade Flow**: Interactive multi-step guide to place custom $N bets on the fly.
- **PnL Analytics**: Daily and session-based profit/loss reporting directly to your phone.

### 🛡️ Production Monitoring & Settlement
- **Watchdog Supervisor**: The `run.py` launcher monitors the bot and performs auto-restarts upon crash or network failures.
- **Simple Redeem Collector**: Integrated system for automatic on-chain settlement of winning positions. Performs a startup check and periodic 5-minute scans.
- **Websocket Watchdog**: Automatic re-connection and staleness detection for 24/7 uptime.

---

## 🏗️ Architecture
```
Fastbot/
├── src/
│   ├── main.py                # Core execution loop (Parallel)
│   ├── data_feed.py           # Multi-market WebSocket client
│   ├── order_executor.py      # Real trading engine with retry logic
│   ├── simple_redeem_collector.py # Robust auto-redeem system
│   ├── strategy.py            # Martingale reversal logic
│   ├── dashboard.py           # Premium Terminal UI (Rich)
│   ├── telegram_bot.py        # Interactive 3x3 menu & UI
│   ├── history_manager.py     # Persistence & PnL tracking
│   └── utils/
│       ├── gsd_logger.py      # Thread-safe logging
│       └── metrics_manager.py # JSON health exporter
├── run.py                     # Watchdog Supervisor (Main Entry)
├── .env                       # Secret keys & Config
└── README.md                  # Comprehensive Documentation
```

---

## ⚙️ Quick Setup
1. **Clone & Setup**:
   ```bash
   git clone https://github.com/satyamsk05/Fastbot.git
   cd Fastbot
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Configure**:
   ```bash
   cp .env.example .env
   # Edit .env with your Polymarket API keys and Wallet PK
   ```
3. **Run**:
   ```bash
   python3 run.py
   ```

---

© 2026 Polymarket Pro Bot Team. Managed via Fastbot Professional Infrastructure.
