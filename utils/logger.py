# --- FILE: utils/logger.py ---
# Hệ thống logging tập trung

import logging
import sys
from datetime import datetime

# Tạo logger
logger = logging.getLogger("KHIBOT")
logger.setLevel(logging.DEBUG)

# Format log
formatter = logging.Formatter(
    '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Các hàm tiện ích
def log_info(message: str):
    """Log thông tin thông thường"""
    logger.info(message)

def log_error(message: str, exc_info=False):
    """Log lỗi"""
    logger.error(message, exc_info=exc_info)

def log_warning(message: str):
    """Log cảnh báo"""
    logger.warning(message)

def log_debug(message: str):
    """Log debug"""
    logger.debug(message)

def log_user_action(user_id: str, user_name: str, action: str, details: str = ""):
    """Log hành động của user"""
    msg = f"[USER:{user_id}] {user_name} | {action}"
    if details:
        msg += f" | {details}"
    logger.info(msg)

def log_game(user_name: str, game: str, bet: int, result: str, profit: int):
    """Log kết quả game"""
    profit_str = f"+{profit}" if profit > 0 else str(profit)
    logger.info(f"[GAME:{game}] {user_name} | Cược:{bet:,} | {result} | {profit_str}")

def log_order(staff_name: str, customer: str, total: int, items_count: int):
    """Log order mới"""
    logger.info(f"[ORDER] {staff_name} | Khách:{customer} | {items_count} món | {total:,}đ")

def log_error_with_context(error: Exception, context: str):
    """Log lỗi với context"""
    logger.error(f"[ERROR] {context} | {type(error).__name__}: {str(error)}", exc_info=True)
