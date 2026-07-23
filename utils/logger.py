import logging
import sys
import os
from datetime import datetime

class ColoredFormatter(logging.Formatter):
    """Цветной форматер для вывода в консоль"""
    
    COLORS = {
        'DEBUG': '\033[94m',      # Blue
        'INFO': '\033[92m',       # Green
        'WARNING': '\033[93m',    # Yellow
        'ERROR': '\033[91m',      # Red
        'CRITICAL': '\033[95m'    # Magenta
    }
    RESET = '\033[0m'

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        format_str = f"{log_color}%(asctime)s - %(name)s - %(levelname)s - %(message)s{self.RESET}"
        formatter = logging.Formatter(format_str, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)

def setup_logger(name: str, log_dir: str = 'logs') -> logging.Logger:
    """Настройка и получение логгера"""
    
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Очистка существующих хэндлеров, чтобы избежать дублирования
    if logger.hasHandlers():
        logger.handlers.clear()
        
    # Консольный хэндлер (цветной)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(ColoredFormatter())
    
    # Файловый хэндлер (детальный, с датой)
    date_str = datetime.now().strftime('%Y-%m-%d')
    file_path = os.path.join(log_dir, f'parser_{date_str}.log')
    
    file_handler = logging.FileHandler(file_path, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger
