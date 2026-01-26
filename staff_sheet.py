# --- FILE: staff_sheet.py ---
# Quản lý nhân viên qua Google Sheet - ĐÃ TỐI ƯU CACHE

import os
import json
import gspread
import random
import time
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

SHEET_NAME = "Trà Sữa Khỉ GG MAP"
STAFF_SHEET_NAME = "Nhân viên"

# === CACHE SYSTEM ===
_staff_cache = None
_cache_time = 0
CACHE_TTL = 300  # Cache 5 phút

_sheet_instance = None
_sheet_time = 0
SHEET_TTL = 600  # Giữ connection 10 phút


def get_staff_sheet():
    """Lấy sheet với connection pooling"""
    global _sheet_instance, _sheet_time
    
    now = time.time()
    
    # Reuse connection nếu còn mới
    if _sheet_instance and (now - _sheet_time) < SHEET_TTL:
        return _sheet_instance
    
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    service_account_info = os.environ.get("GOOGLE_SERVICE_ACCOUNT")
    
    if service_account_info:
        creds_dict = json.loads(service_account_info)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
    
    client = gspread.authorize(creds)
    spreadsheet = client.open(SHEET_NAME)
    
    try:
        sheet = spreadsheet.worksheet(STAFF_SHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title=STAFF_SHEET_NAME, rows=100, cols=10)
        sheet.append_row(["PIN", "Tên", "SĐT", "Telegram_ID", "Ngày đăng ký"])
        print(f"✅ Đã tạo sheet '{STAFF_SHEET_NAME}'")
    
    _sheet_instance = sheet
    _sheet_time = now
    return sheet


def get_all_staff_cached():
    """Lấy danh sách nhân viên CÓ CACHE - NHANH"""
    global _staff_cache, _cache_time
    
    now = time.time()
    
    # Trả về cache nếu còn mới
    if _staff_cache is not None and (now - _cache_time) < CACHE_TTL:
        return _staff_cache
    
    # Refresh cache
    sheet = get_staff_sheet()
    _staff_cache = sheet.get_all_records()
    _cache_time = now
    return _staff_cache


def clear_cache():
    """Xóa cache khi có thay đổi dữ liệu"""
    global _staff_cache, _cache_time
    _staff_cache = None
    _cache_time = 0


def generate_pin():
    """Sinh PIN 4 số ngẫu nhiên, đảm bảo không trùng"""
    records = get_all_staff_cached()
    existing_pins = [str(r.get("PIN")) for r in records]
    
    while True:
        pin = str(random.randint(1000, 9999))
        if pin not in existing_pins:
            return pin


def get_all_staff():
    """Lấy danh sách tất cả nhân viên (dùng cache)"""
    return get_all_staff_cached()


def get_staff_by_pin(pin: str):
    """Tìm nhân viên theo PIN - NHANH với cache"""
    records = get_all_staff_cached()
    pin_str = str(pin)
    for r in records:
        if str(r.get("PIN")) == pin_str:
            return r
    return None


def get_staff_by_telegram(telegram_id: str):
    """Tìm nhân viên theo Telegram ID - NHANH với cache"""
    records = get_all_staff_cached()
    tg_str = str(telegram_id)
    for r in records:
        if str(r.get("Telegram_ID")) == tg_str:
            return r
    return None


def get_staff_by_phone(phone: str):
    """Tìm nhân viên theo SĐT - NHANH với cache"""
    records = get_all_staff_cached()
    phone_str = str(phone)
    for r in records:
        if str(r.get("SĐT")) == phone_str:
            return r
    return None


def register_staff(name: str, phone: str, telegram_id: str):
    """
    Đăng ký nhân viên mới hoặc cập nhật thông tin
    Returns: (success: bool, message: str, pin: str or None)
    """
    # Kiểm tra SĐT đã tồn tại với người khác chưa
    existing_by_phone = get_staff_by_phone(phone)
    if existing_by_phone and str(existing_by_phone.get("Telegram_ID")) != str(telegram_id):
        return False, "SĐT này đã được đăng ký bởi người khác!", None
    
    # Kiểm tra Telegram ID đã đăng ký chưa
    existing_by_tg = get_staff_by_telegram(telegram_id)
    
    sheet = get_staff_sheet()
    
    if existing_by_tg:
        # Cập nhật thông tin (ghi đè)
        pin = str(existing_by_tg.get("PIN"))
        records = get_all_staff_cached()
        for i, r in enumerate(records):
            if str(r.get("Telegram_ID")) == str(telegram_id):
                row_num = i + 2
                sheet.update_cell(row_num, 2, name)
                sheet.update_cell(row_num, 3, phone)
                break
        
        clear_cache()  # Xóa cache sau khi thay đổi
        return True, f"Đã cập nhật thông tin! PIN của bạn vẫn là: {pin}", pin
    else:
        # Tạo mới
        pin = generate_pin()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        sheet.append_row([pin, name, phone, str(telegram_id), now])
        
        clear_cache()  # Xóa cache sau khi thay đổi
        return True, f"Đăng ký thành công! PIN của bạn là: {pin}", pin


def delete_staff(pin: str):
    """Xóa nhân viên theo PIN (Admin only)"""
    sheet = get_staff_sheet()
    records = get_all_staff_cached()
    
    for i, r in enumerate(records):
        if str(r.get("PIN")) == str(pin):
            row_num = i + 2
            staff_name = r.get('Tên')
            sheet.delete_rows(row_num)
            
            clear_cache()  # Xóa cache sau khi thay đổi
            return True, f"Đã xóa nhân viên: {staff_name}"
    
    return False, "Không tìm thấy PIN này!"


def get_staff_count():
    """Đếm số nhân viên"""
    records = get_all_staff_cached()
    return len(records)
