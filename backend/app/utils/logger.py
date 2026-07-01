import logging
import os
from logging.handlers import RotatingFileHandler

# Log file path: /home/mihir_p_a/Documents/project/stocksense/backend/stocksense.log
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(BASE_DIR, "stocksense.log")

def setup_logger():
    # Get root-level logger for the app
    logger = logging.getLogger("stocksense")
    logger.setLevel(logging.INFO)

    # Avoid adding duplicate handlers if the logger is re-initialized (e.g. during reload)
    if logger.handlers:
        return logger

    # Formatter: [Timestamp] LEVEL [File:Line] - Message
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console Handler (writes to terminal stdout)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating File Handler (writes to backend/stocksense.log, rotating when file reaches 10MB)
    try:
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,              # Keep up to 5 historical log files
            encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not create log file handler: {e}")

    return logger

# Globally accessible logger instance
logger = setup_logger()
