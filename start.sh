#!/bin/bash

# ╔══════════════════════════════════════════════════════════╗
# ║   FASTBOT: Automatic Runner v1.0                         ║
# ║   Auto-activates VENV and starts the supervisor.         ║
# ╚══════════════════════════════════════════════════════════╝

ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$ROOT_DIR"

echo "🚀 Starting Fastbot..."

# 1. Check for Virtual Environment
if [ -d "venv" ]; then
    echo "📦 Activating virtual environment..."
    source venv/bin/activate
else
    echo "⚠️  Warning: venv not found. Running with system python."
fi

# 2. Export environment (optional)
export PYTHONPATH="$ROOT_DIR/src:$PYTHONPATH"

# 3. Start the watchdog/supervisor
# We use 'exec' so signals (SIGINT) go directly to the supervisor
echo "🛰️  Launching Terminal Dashboard..."
exec python3 run.py
