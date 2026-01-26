# --- FILE: database.py ---
import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Giữ nguyên cấu hình DATABASE_URL và engine cũ của bạn
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL.startswith("postgres://"):
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

# --- CẬP NHẬT BẢNG EMPLOYEE (Thêm coin và last_daily) ---
class Employee(Base):
    __tablename__ = "employees"
    telegram_id = Column(String, primary_key=True, index=True) 
    name = Column(String)
    emoji = Column(String, unique=True)
    balance = Column(Float, default=0.0)    # Tiền Lương (VND)
    coin = Column(Float, default=0.0)       # Tiền Game (Xu) - MỚI
    last_daily = Column(DateTime, nullable=True) # Thời gian điểm danh gần nhất - MỚI
    last_checkin = Column(Date, nullable=True)
    checkin_streak = Column(Integer, default=0)
    last_gift_open = Column(Date, nullable=True)

# --- THÊM BẢNG LỊCH SỬ ĐỔI QUÀ (SHOP) ---
class ShopLog(Base):
    __tablename__ = "shop_logs"
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(String)
    item_name = Column(String)
    cost = Column(Float)
    created_at = Column(DateTime, default=datetime.now)
    status = Column(String, default="pending") # pending: chờ duyệt, done: đã trao

def init_db():
    Base.metadata.create_all(bind=engine)

