# --- FILE: database.py ---
import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Float, Date, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Giữ nguyên cấu hình DATABASE_URL và engine cũ của bạn
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL, 
    pool_pre_ping=True, pool_recycle=300, pool_size=10, max_overflow=20,
    connect_args={"keepalives": 1, "keepalives_idle": 30, "keepalives_interval": 10, "keepalives_count": 5}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- CÁC BẢNG CŨ (Review, ReviewLog) GIỮ NGUYÊN ---
class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True, index=True)
    content = Column(String, nullable=False)
    is_used = Column(Boolean, default=False)

class ReviewLog(Base):
    __tablename__ = "review_logs"
    id = Column(Integer, primary_key=True, index=True)
    google_review_id = Column(String, unique=True, index=True)
    reviewer_name = Column(String)
    content = Column(String)
    stars = Column(Integer)
    staff_id = Column(String)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.now)

# --- BẢNG EMPLOYEE (ĐẦY ĐỦ) ---
class Employee(Base):
    __tablename__ = "employees"
    telegram_id = Column(String, primary_key=True, index=True) 
    name = Column(String)
    emoji = Column(String, unique=True)
    balance = Column(Float, default=0.0)        # Tiền Lương (VND)
    coin = Column(Float, default=0.0)           # Tiền Game (Xu)
    last_daily = Column(DateTime, nullable=True) # Thời gian điểm danh gần nhất (cũ)
    last_checkin = Column(Date, nullable=True)   # Ngày điểm danh (mới - cho streak)
    checkin_streak = Column(Integer, default=0)  # Số ngày liên tục
    last_gift_open = Column(Date, nullable=True) # Ngày mở quà gần nhất

# --- BẢNG LỊCH SỬ ĐỔI QUÀ (SHOP) ---
class ShopLog(Base):
    __tablename__ = "shop_logs"
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(String)
    item_name = Column(String)
    cost = Column(Float)
    created_at = Column(DateTime, default=datetime.now)
    status = Column(String, default="pending")

def init_db():
    Base.metadata.create_all(bind=engine)

# === AUTO MIGRATE - Thêm cột mới nếu chưa có ===
def migrate_db():
    """Tự động thêm các cột mới vào database"""
    try:
        inspector = inspect(engine)
        
        # Kiểm tra bảng employees có tồn tại không
        if 'employees' not in inspector.get_table_names():
            print("⏳ Bảng employees chưa tồn tại, sẽ được tạo khi init_db()")
            return
        
        columns = [col['name'] for col in inspector.get_columns('employees')]
        
        with engine.connect() as conn:
            if 'last_checkin' not in columns:
                conn.execute(text('ALTER TABLE employees ADD COLUMN last_checkin DATE'))
                conn.commit()
                print("✅ Đã thêm cột last_checkin")
            
            if 'checkin_streak' not in columns:
                conn.execute(text('ALTER TABLE employees ADD COLUMN checkin_streak INTEGER DEFAULT 0'))
                conn.commit()
                print("✅ Đã thêm cột checkin_streak")
            
            if 'last_gift_open' not in columns:
                conn.execute(text('ALTER TABLE employees ADD COLUMN last_gift_open DATE'))
                conn.commit()
                print("✅ Đã thêm cột last_gift_open")
                
        print("✅ Database migration hoàn tất!")
        
    except Exception as e:
        print(f"⚠️ Migration warning: {e}")

# Chạy migrate khi import module
migrate_db()
