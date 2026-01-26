# --- FILE: staff_sheet.py ---
# Quản lý nhân viên qua Google Sheet

import os
import json
import gspread
import random
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

SHEET_NAME = "Trà Sữa Khỉ GG MAP"
STAFF_SHEET_NAME = "Nhân viên"

def get_staff_sheet():
    """Lấy sheet Nhân viên, tạo mới nếu chưa có"""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Đọc credentials từ Environment Variable (Render) hoặc file (local)
    service_account_info = os.environ.get("GOOGLE_SERVICE_ACCOUNT")
    
    if service_account_info:
        # Chạy trên Render (dùng ENV)
        creds_dict = json.loads(service_account_info)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        # Chạy local (dùng file)
        creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
    
    client = gspread.authorize(creds)
    spreadsheet = client.open(SHEET_NAME)
    
    # Tìm hoặc tạo sheet "Nhân viên"
    try:
        sheet = spreadsheet.worksheet(STAFF_SHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        # Tạo sheet mới với header
        sheet = spreadsheet.add_worksheet(title=STAFF_SHEET_NAME, rows=100, cols=10)
        sheet.append_row(["PIN", "Tên", "SĐT", "Telegram_ID", "Ngày đăng ký"])
        print(f"✅ Đã tạo sheet '{STAFF_SHEET_NAME}'")
    
    return sheet

def generate_pin():
    """Sinh PIN 4 số ngẫu nhiên, đảm bảo không trùng"""
    sheet = get_staff_sheet()
    existing_pins = sheet.col_values(1)[1:]  # Bỏ header
    
    while True:
        pin = str(random.randint(1000, 9999))
        if pin not in existing_pins:
            return pin

def get_all_staff():
    """Lấy danh sách tất cả nhân viên"""
    sheet = get_staff_sheet()
    records = sheet.get_all_records()
    return records

def get_staff_by_pin(pin: str):
    """Tìm nhân viên theo PIN"""
    sheet = get_staff_sheet()
    records = sheet.get_all_records()
    for r in records:
        if str(r.get("PIN")) == str(pin):
            return r
    return None

def get_staff_by_telegram(telegram_id: str):
    """Tìm nhân viên theo Telegram ID"""
    sheet = get_staff_sheet()
    records = sheet.get_all_records()
    for r in records:
        if str(r.get("Telegram_ID")) == str(telegram_id):
            return r
    return None

def get_staff_by_phone(phone: str):
    """Tìm nhân viên theo SĐT"""
    sheet = get_staff_sheet()
    records = sheet.get_all_records()
    for r in records:
        if str(r.get("SĐT")) == str(phone):
            return r
    return None

def register_staff(name: str, phone: str, telegram_id: str):
    """
    Đăng ký nhân viên mới hoặc cập nhật thông tin
    Returns: (success: bool, message: str, pin: str or None)
    """
    sheet = get_staff_sheet()
    
    # Kiểm tra SĐT đã tồn tại với người khác chưa
    existing_by_phone = get_staff_by_phone(phone)
    if existing_by_phone and str(existing_by_phone.get("Telegram_ID")) != str(telegram_id):
        return False, "SĐT này đã được đăng ký bởi người khác!", None
    
    # Kiểm tra Telegram ID đã đăng ký chưa
    existing_by_tg = get_staff_by_telegram(telegram_id)
    
    if existing_by_tg:
        # Cập nhật thông tin (ghi đè)
        pin = str(existing_by_tg.get("PIN"))
        records = sheet.get_all_records()
        for i, r in enumerate(records):
            if str(r.get("Telegram_ID")) == str(telegram_id):
                row_num = i + 2  # +1 for header, +1 for 0-index
                sheet.update_cell(row_num, 2, name)  # Cột Tên
                sheet.update_cell(row_num, 3, phone)  # Cột SĐT
                break
        return True, f"Đã cập nhật thông tin! PIN của bạn vẫn là: {pin}", pin
    else:
        # Tạo mới
        pin = generate_pin()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        sheet.append_row([pin, name, phone, str(telegram_id), now])
        return True, f"Đăng ký thành công! PIN của bạn là: {pin}", pin

def delete_staff(pin: str):
    """Xóa nhân viên theo PIN (Admin only)"""
    sheet = get_staff_sheet()
    records = sheet.get_all_records()
    
    for i, r in enumerate(records):
        if str(r.get("PIN")) == str(pin):
            row_num = i + 2  # +1 for header, +1 for 0-index
            sheet.delete_rows(row_num)
            return True, f"Đã xóa nhân viên: {r.get('Tên')}"
    
    return False, "Không tìm thấy PIN này!"

def get_staff_count():
    """Đếm số nhân viên"""
    sheet = get_staff_sheet()
    records = sheet.get_all_records()
    return len(records)
