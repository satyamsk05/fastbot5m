import os
import json
import time
import threading
import logging
from datetime import datetime
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
# METRICS MANAGER - Standardized Observability for High-Frequency Bots
# ═══════════════════════════════════════════════════════════════════════════════

_metrics = {
    "status": "starting",
    "uptime_seconds": 0,
    "last_update": 0,
    "version": "2.0.0",
    "trades": {
        "total": 0,
        "wins": 0,
        "losses": 0,
        "win_rate": 0.0
    },
    "pnl": {
        "daily": 0.0,
        "total": 0.0
    },
    "balances": {
        "usdc": 0.0,
        "matic": 0.0,
        "virtual": 0.0
    },
    "health": {
        "ws_connected": False,
        "last_heartbeat": 0,
        "errors_24h": 0
    }
}

_lock = threading.Lock()
_metrics_file = "data/metrics.json"
_stop_event = threading.Event()
_start_time = time.time()

def update_metric(category, key, value):
    """Updates a specific metric in a thread-safe manner."""
    global _metrics
    with _lock:
        if category in _metrics:
            if isinstance(_metrics[category], dict):
                _metrics[category][key] = value
            else:
                _metrics[category] = value
        else:
            _metrics[key] = value
        _metrics["last_update"] = int(time.time())

def increment_trade(won: bool):
    """Increments trade count and updates win rate."""
    with _lock:
        t = _metrics["trades"]
        t["total"] += 1
        if won: t["wins"] += 1
        else: t["losses"] += 1
        if t["total"] > 0:
            t["win_rate"] = round(t["wins"] / t["total"] * 100, 2)
        _metrics["last_update"] = int(time.time())

def set_health_state(ws_connected: bool):
    """Updates system health state."""
    update_metric("health", "ws_connected", ws_connected)
    update_metric("health", "last_heartbeat", int(time.time()))

def _save_loop():
    """Background thread to periodically save metrics to disk."""
    while not _stop_event.is_set():
        try:
            with _lock:
                _metrics["uptime_seconds"] = int(time.time() - _start_time)
                # Atomic write
                tmp_file = f"{_metrics_file}.tmp"
                with open(tmp_file, "w") as f:
                    json.dump(_metrics, f, indent=4)
                os.replace(tmp_file, _metrics_file)
        except Exception as e:
            logging.error(f"[METRICS] Failed to save: {e}")
        
        # Save every 30 seconds
        for _ in range(30):
            if _stop_event.is_set(): break
            time.sleep(1)

def init_metrics():
    """Initializes the metrics manager and starts the background saver."""
    os.makedirs(os.path.dirname(_metrics_file), exist_ok=True)
    threading.Thread(target=_save_loop, daemon=True, name="metrics-saver").start()
    logging.info("Metrics Manager Initialized")

def get_metrics_json():
    """Returns the current metrics as a JSON string for API endpoints."""
    with _lock:
        return json.dumps(_metrics)

def stop_metrics():
    """Gracefully shuts down the metrics manager."""
    _stop_event.set()
    update_metric(None, "status", "stopped")
