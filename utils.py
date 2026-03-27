"""
utils.py — Utilities, Logger Setup, Helpers
"""

import logging
import sys
from datetime import datetime


def setup_logger(name: str = 'dahlah7', level: str = 'INFO') -> logging.Logger:
    """Setup application logger with console and file handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG)
    console_fmt = logging.Formatter(
        '%(asctime)s │ %(levelname)-7s │ %(message)s',
        datefmt='%H:%M:%S'
    )
    console.setFormatter(console_fmt)
    logger.addHandler(console)

    # File handler
    log_filename = f"dahlah7_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        '%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_fmt)
    logger.addHandler(file_handler)

    return logger


def format_price(price: float, decimals: int = 4) -> str:
    """Format price with specified decimals."""
    return f"{price:.{decimals}f}"


def timeframe_to_seconds(tf: str) -> int:
    """Convert timeframe string to seconds."""
    multipliers = {
        'm': 60, 'h': 3600, 'd': 86400, 'w': 604800
    }
    unit = tf[-1].lower()
    number = int(tf[:-1])
    return number * multipliers.get(unit, 60)


def print_banner():
    """Print startup banner."""
    banner = """
╔═════════════════════════════════════════════════════╗
║                                                     ║
║    ██████╗  █████╗ ██╗  ██╗██╗      █████╗ ██╗  ██╗ ║
║    ██╔══██╗██╔══██╗██║  ██║██║     ██╔══██╗██║  ██║ ║
║    ██║  ██║███████║███████║██║     ███████║███████║ ║
║    ██║  ██║██╔══██║██╔══██║██║     ██╔══██║██╔══██║ ║
║    ██████╔╝██║  ██║██║  ██║███████╗██║  ██║██║  ██║ ║
║    ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝ ║
║                                                     ║
╚═════════════════════════════════════════════════════╝
    """
    print(banner)