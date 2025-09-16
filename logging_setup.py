# logging_setup.py - Upravená verzia pre šetrenie SD karty
import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logging():
    """
    Nastavuje minimálny logging pre šetrenie SD karty.
    - Iba kritické chyby sa zapisujú na disk
    - DEBUG a INFO správy len do pamäte
    - Výrazne znížená frekvencia zápisu
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(script_dir, 'logs')
    
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Vytvoríme vlastný handler pre kritické chyby
    log_file = os.path.join(log_dir, 'critical_errors.log')
    
    # Iba pre CRITICAL a ERROR správy - výrazne menej zápisov
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # Znížené na 5MB
        backupCount=2              # Iba 2 backup súbory
    )
    file_handler.setLevel(logging.ERROR)  # Iba ERROR a vyššie
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    
    # In-memory handler pre DEBUG/INFO (nezapisuje na disk)
    memory_handler = logging.StreamHandler()
    memory_handler.setLevel(logging.INFO)
    memory_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    
    # Nastavenie root logger-a
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Vyčistenie starých handler-ov
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Pridanie našich handler-ov
    root_logger.addHandler(file_handler)
    # Poznámka: memory_handler sa nepridáva, pretože StreamHandler zapisuje na stdout
    # čo môže byť zachytené systemd, ale nepisuje na SD kartu
    
    # Špecifické nastavenia pre rôzne moduly - zníženie úrovne logovania
    logging.getLogger('audio_manager').setLevel(logging.WARNING)
    logging.getLogger('button_handler').setLevel(logging.WARNING)
    logging.getLogger('looper_engine').setLevel(logging.WARNING)
    logging.getLogger('stats_collector').setLevel(logging.ERROR)  # Stats sa zapisujú aj tak
    
    logging.error("Minimal logging setup complete - saving SD card wear")
    logging.error(f"Critical errors logged to: {log_file}")