import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# --- DÁN LINK NEON CỦA BẠN VÀO ĐÂY ---
DATABASE_URL = "postgresql://neondb_owner:npg_f1MbRLZmo4PJ@ep-flat-recipe-a1f9rbiq-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require" 

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Thêm pool_pre_ping=True để tự động nối lại khi bị ngắt
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True, index=True)
    content = Column(String, nullable=False)
    is_used = Column(Boolean, default=False)

class Employee(Base):
    __tablename__ = "employees"
    telegram_id = Column(String, primary_key=True, index=True) 
    name = Column(String)
    emoji = Column(String, unique=True)
    balance = Column(Float, default=0.0)

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

def init_db():
    Base.metadata.create_all(bind=engine)
