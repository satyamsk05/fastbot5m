#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║   FASTBOT: Watchdog Supervisor v2.5                      ║
║   Auto-restarts the Fastbot suite upon crash.            ║
╚══════════════════════════════════════════════════════════╝
"""
import sys
import os
import time
import subprocess
import signal
import logging
from datetime import datetime

# ── Configuration ─────────────────────────────────────────────
RESTART_DELAY = 5       # Seconds to wait before restarting
MAX_RETRIES = 10        # Max consecutive crashes before giving up
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Setup basic logging for the supervisor itself
os.makedirs(os.path.join(ROOT_DIR, "logs"), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [WATCHDOG] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(ROOT_DIR, "logs/watchdog.log")),
        logging.StreamHandler()
    ]
)

def run_bot():
    """Runs the main bot process and returns the exit code."""
    env = os.environ.copy()
    # Ensure src/ is in PYTHONPATH for the child process
    src_path = os.path.join(ROOT_DIR, "src")
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"{src_path}:{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = src_path

    # Detect VENV interpreter
    venv_python = os.path.join(ROOT_DIR, "venv", "bin", "python3")
    py_exec = venv_python if os.path.exists(venv_python) else sys.executable
    
    cmd = [py_exec, os.path.join(ROOT_DIR, "main.py")]
    
    try:
        process = subprocess.Popen(cmd, env=env)
        return process
    except Exception as e:
        logging.error(f"Failed to start bot process: {e}")
        return None

def main():
    os.chdir(ROOT_DIR)
    
    retry_count = 0
    last_restart_time = 0
    
    logging.info("Supervisor started. Monitoring Polymarket Bot...")

    while retry_count < MAX_RETRIES:
        start_time = time.time()
        process = run_bot()
        
        if process is None:
            retry_count += 1
            time.sleep(RESTART_DELAY)
            continue

        try:
            # Wait for the process to exit
            exit_code = process.wait()
            
            if exit_code == 0:
                logging.info("Bot exited gracefully (code 0). Stopping supervisor.")
                break
            elif exit_code == -signal.SIGINT or exit_code == -signal.SIGTERM:
                logging.info(f"Bot terminated by signal {exit_code}. stopping supervisor.")
                break
            else:
                uptime = time.time() - start_time
                logging.error(f"Bot crashed with exit code {exit_code} after {uptime:.1f}s")
                
                # Reset retry count if it ran for more than 5 minutes
                if uptime > 300:
                    retry_count = 0
                else:
                    retry_count += 1
                
                if retry_count >= MAX_RETRIES:
                    logging.critical("Max retries reached. supervisor giving up.")
                    break
                
                logging.info(f"Restarting in {RESTART_DELAY}s (Attempt {retry_count}/{MAX_RETRIES})...")
                time.sleep(RESTART_DELAY)
                
        except KeyboardInterrupt:
            logging.info("Watchdog received KeyboardInterrupt. Terminating bot...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            break

    logging.info("Supervisor stopped.")

if __name__ == "__main__":
    main()
