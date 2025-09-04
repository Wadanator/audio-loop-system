# logging_setup.py
import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logging():
    """
    Sets up logging with rotation to an internal log file, without console output.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(script_dir, 'logs')
    
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, 'app.log')
    
    rotating_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5
    )
    rotating_handler.setLevel(logging.INFO)
    rotating_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    root_logger.addHandler(rotating_handler)
    
    logging.info("Logging setup complete - file only logging (10MB max per file, 5 backups)")
    logging.info(f"Log file location: {log_file}")