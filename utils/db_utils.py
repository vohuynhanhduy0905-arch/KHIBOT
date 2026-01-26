# --- FILE: utils/db_utils.py ---
# Database utilities - Fix session leak với context manager

from contextlib import contextmanager
from database import SessionLocal, Employee
from utils.logger import log_error_with_context

@contextmanager
def get_db():
    """
    Context manager để quản lý database session.
    Tự động đóng session khi xong hoặc khi có lỗi.
    
    Usage:
        with get_db() as db:
            emp = db.query(Employee).filter(...).first()
            emp.coin += 1000
            db.commit()
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        log_error_with_context(e, "Database error")
        raise
    finally:
        db.close()


def get_employee(telegram_id: str) -> Employee | None:
    """Lấy employee theo telegram_id"""
    with get_db() as db:
        return db.query(Employee).filter(Employee.telegram_id == str(telegram_id)).first()


def get_employee_safe(db, telegram_id: str) -> Employee | None:
    """Lấy employee trong session có sẵn"""
    return db.query(Employee).filter(Employee.telegram_id == str(telegram_id)).first()


def update_employee_coin(telegram_id: str, amount: int, reason: str = "") -> tuple[bool, int]:
    """
    Cập nhật coin của employee.
    Returns: (success, new_balance)
    """
    with get_db() as db:
        emp = db.query(Employee).filter(Employee.telegram_id == str(telegram_id)).first()
        if not emp:
            return False, 0
        
        emp.coin += amount
        db.commit()
        return True, emp.coin


def update_employee_balance(telegram_id: str, amount: int) -> tuple[bool, float]:
    """
    Cập nhật balance (lương) của employee.
    Returns: (success, new_balance)
    """
    with get_db() as db:
        emp = db.query(Employee).filter(Employee.telegram_id == str(telegram_id)).first()
        if not emp:
            return False, 0
        
        emp.balance += amount
        db.commit()
        return True, emp.balance


def check_and_deduct_coin(telegram_id: str, amount: int) -> tuple[bool, int]:
    """
    Kiểm tra và trừ coin nếu đủ.
    Returns: (success, remaining_coin)
    """
    with get_db() as db:
        emp = db.query(Employee).filter(Employee.telegram_id == str(telegram_id)).first()
        if not emp or emp.coin < amount:
            return False, emp.coin if emp else 0
        
        emp.coin -= amount
        db.commit()
        return True, emp.coin
