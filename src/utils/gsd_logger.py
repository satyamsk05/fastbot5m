import os
import sys
import logging
import logging.handlers
import threading
import queue
from pathlib import Path
from datetime import datetime

# ═══════════════════════════════════════════════════════════════════════════════
# GSD LOGGER - Thread-safe, non-blocking logging for High-Frequency Bots
# ═══════════════════════════════════════════════════════════════════════════════

_log_queue = queue.Queue(-1)  # Unlimited size
_listener = None
_initialized = False
_lock = threading.Lock()

def setup_gsd_logging(log_file="logs/bot.log", level=logging.INFO):
    """
    Initializes the centralized, queue-based logging system.
    This should be called ONCE at the very entry point of the application.
    """
    global _initialized, _listener
    with _lock:
        if _initialized:
            return
        
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # 1. Dedicated formatters
        standard_format = logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(threadName)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        # 2. Handlers that will actually write (used by Listener)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(standard_format)
        
        # 3. Create the Listener to process the queue in a background thread
        _listener = logging.handlers.QueueListener(
            _log_queue, 
            file_handler,
            respect_handler_level=True
        )
        _listener.start()
        
        # 4. Configure the root logger to use the QueueHandler
        root = logging.getLogger()
        root.setLevel(level)
        
        # Remove any existing handlers to prevent duplication
        for handler in root.handlers[:]:
            root.removeHandler(handler)
            
        queue_handler = logging.handlers.QueueHandler(_log_queue)
        root.addHandler(queue_handler)
        
        # Silence noisy libraries
        for lib in ["urllib3", "requests", "httpx", "telegram", "apscheduler", "web3", "py_clob_client"]:
            logging.getLogger(lib).setLevel(logging.WARNING)
            
        # 5. Global Exception Hook
        sys.excepthook = handle_exception
        
        _initialized = True
        logging.info("GSD Centralized Logging Initialized (Queue-based)")

def handle_exception(exc_type, exc_value, exc_traceback):
    """Log any uncaught exceptions."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    import traceback
    traceback.print_exception(exc_type, exc_value, exc_traceback)
    logging.critical("Uncaught Exception", exc_info=(exc_type, exc_value, exc_traceback))

def get_gsd_logger(name: str):
    """Returns a logger instance for the given name."""
    if not _initialized:
        # Fallback to standard if not yet initialized, but warn
        setup_gsd_logging()
    return logging.getLogger(name)

def stop_gsd_logging():
    """Shuts down the logging listener gracefully."""
    global _listener
    if _listener:
        logging.info("Shutting down logging listener...")
        _listener.stop()
        _listener = None

# GSD Audit Trail for verify/audit workflows
def log_audit(message: str):
    """Special log for GSD Audit Trail."""
    audit_logger = get_gsd_logger("GSD.AUDIT")
    audit_logger.info(f"► {message}")
