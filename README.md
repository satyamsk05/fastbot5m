# 💎 FASTBOT: Polymarket 5m Streak-Reversal Suite v3.0

[![Status](https://img.shields.io/badge/Status-Production--Ready-brightgreen)](https://github.com/satyamsk05/fastbot5m)
[![Version](https://img.shields.io/badge/Version-3.0.0-blue)](https://github.com/satyamsk05/fastbot5m)
[![Strategy](https://img.shields.io/badge/Strategy-5m--Martingale--Reversal-orange)](https://github.com/satyamsk05/fastbot5m)
[![Network](https://img.shields.io/badge/Network-Polygon-blueviolet)](https://github.com/satyamsk05/fastbot5m)

A professional-grade, high-performance trading suite for Polymarket. **Fastbot** is engineered for 24/7 autonomous operation, combining low-latency entry with a battle-tested **5-minute streak-reversal** strategy and a resilient **Martingale** recovery engine.

---

## ⚡ Core Trading Strategy (The 5m Edge)

Fastbot operates exclusively on **5-minute market intervals**, providing significantly more trading opportunities and more consistent trend-exhaustion entry points compared to standard 15m or 1h markets.

### 📊 1. Signal Detection Logic
The bot continuously monitors real-time price feeds for **BTC, ETH, SOL, and XRP**.
- **The Streak**: The bot looks for **3+ consecutive same-direction candle closes** (e.g., three 🟢 UP candles).
- **The Reversal**: Once a streak is confirmed at the 5m boundary, the bot executes a **Mean-Reversion Trade** in the opposite direction.
- **The Buffer**: Implements a configurable **settlement buffer** (default 5s) to ensure candles are fully finalized on-chain before calculating signals.

### 🪜 2. Martingale Recovery Ladder
To hedge against momentary trend extensions, Fastbot utilizes an optimized recovery ladder:
- **Default Steps**: `$3 → $6 → $13 → $28 → $60 USDC`.
- **Level Reset**: Resets to Step 1 immediately after any **WIN** or upon reaching the max ladder level to protect long-term capital.
- **Persistence**: Tracks the current step for every coin independently in `data/martingale_state.json`.

### 🎯 3. Optimized Execution Brackets
Fastbot uses two distinct pricing strategies to maximize fill rates and minimize slippage:
- **L1 (Discovery)**: Entry orders (Step 0) are placed within a **0.40–0.60 USDC** bracket using **FOK (Fill or Kill)** logic.
- **L2-L5 (Recovery)**: Scaling orders are locked within a tighter **0.47–0.54 USDC** bracket using **GTC (Good 'Til Canceled)** logic.
- **Strategic Buying**: By capping recovery prices at `0.54`, the bot effectively "waits" for the best possible entry, ensuring favorable ROI on recovery trades.

---

## 🏗️ Technical Components

| Component | Description |
|-----------|-------------|
| **`OrderExecutor`** | Handles FOK/GTC order types, chunking, and smart retries with price normalization. |
| **`SafetyGuard`** | Enforces max order size, investment limits, and order frequency protection. |
| **`SimpleRedeemCollector`** | Background thread that automatically settles winning positions on-chain every 5 minutes. |
| **`Watchdog Supervisor`** | Monitor process (`run.py`) that auto-restarts the bot upon crash or network failure. |

---

## 🚀 Key Features

- **🚀 4Hz Dashboard**: A high-refresh terminal UI providing real-time PnL, streak counters, and market timers.
- **📱 Telegram Interactive Bot**: A full 3x3 menu command center allowing you to check balances, view open positions, and place manual trades from your phone.
- **🛡️ Risk Management**: Built-in protection against over-trading, price outliers, and excessive drawdown.
- **💾 Full Persistence**: State-aware architecture resumes instantly after restarts without losing Martingale steps or trade history.

---

## 🏗️ Architecture & File Structure
```
fastbot5m/
├── main.py                # Core parallel execution loop & system wiring
├── run.py                 # Watchdog Supervisor (Main Entry Point)
├── config/
│   └── default.json       # Advanced strategy & execution parameters
├── data/                  # Persistent state (Martingale, Virtual Balance)
├── history/               # Local SQLite/JSON trade history & PnL logs
├── src/                   # Core Module Logic
│   ├── data_feed.py       # Polymarket WebSocket sync
│   ├── trader.py          # Market-specific logic & PnL calculation
│   ├── dashboard.py       # Rich terminal visualization
│   └── telegram_bot.py    # Telegram command handlers & Menu UI
└── .env                   # API Keys, Private Keys, and Environment Settings
```

---

## ⚙️ Quick Setup

1. **Environment Initialization**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configuration**: 
   - Copy `.env.example` to `.env`.
   - Add your **Polymarket API Key, Secret, Passphrase, and Private Key**.
   - Set `DRY_RUN=true` for initial paper trading.

3. **Execution**:
   ```bash
   python3 run.py
   ```

---

## ⚠️ Risk Disclaimer
Trading involves significant risk. This bot is a tool for professional traders. Always start with `DRY_RUN=true` to understand market dynamics and never trade with funds you cannot afford to lose.

---
© 2026 Fastbot Infrastructure Team. Built for Polymarket Professional Traders.
