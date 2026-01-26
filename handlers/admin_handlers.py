# --- FILE: handlers/admin_handlers.py ---
# Xử lý các lệnh admin

from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_ID
from database import SessionLocal, Employee
from staff_sheet import register_staff, delete_staff, get_all_staff, get_staff_count
from utils import get_db, log_info, log_user_action


# ==========================================
# /dangky - Đăng ký nhân viên
# ==========================================

async def dangky_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Đăng ký nhân viên mới"""
    user = update.effective_user
    args = context.args
    
    # Hiển thị hướng dẫn nếu không có tham số
    if not args or len(args) < 2:
        await update.message.reply_text(
            "📝 <b>ĐĂNG KÝ NHÂN VIÊN</b>\n\n"
            "Cú pháp: /dangky Tên SĐT\n"
            "Ví dụ: /dangky Lan 0901234567\n\n"
            "⚠️ Lưu ý:\n"
            "• Tên không có dấu cách (dùng _ nếu cần)\n"
            "• SĐT phải là số điện thoại hợp lệ",
            parse_mode="HTML"
        )
        return
    
    name = args[0].replace("_", " ")
    phone = args[1]
    
    # Validate số điện thoại
    if not phone.isdigit() or len(phone) < 9:
        await update.message.reply_text("❌ Số điện thoại không hợp lệ!")
        return
    
    # Đăng ký
    success, message, pin = register_staff(name, phone, str(user.id))
    
    if success:
        log_user_action(str(user.id), name, "ĐĂNG KÝ", f"PIN: {pin}, SĐT: {phone}")
        await update.message.reply_text(
            f"✅ <b>{message}</b>\n\n"
            f"📌 Lưu lại PIN này để đăng nhập webapp!\n"
            f"🔐 PIN: <code>{pin}</code>",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(f"❌ {message}")


# ==========================================
# /dsnv - Danh sách nhân viên (Admin)
# ==========================================

async def dsnv_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xem danh sách nhân viên (Admin only)"""
    user = update.effective_user
    
    if str(user.id) != ADMIN_ID:
        await update.message.reply_text("❌ Chỉ Admin mới dùng được lệnh này!")
        return
    
    staff_list = get_all_staff()
    
    if not staff_list:
        await update.message.reply_text("📋 Chưa có nhân viên nào đăng ký!")
        return
    
    txt = f"📋 <b>DANH SÁCH NHÂN VIÊN</b> ({len(staff_list)} người)\n"
    txt += "━━━━━━━━━━━━━━━━\n"
    
    for i, s in enumerate(staff_list, 1):
        pin = s.get("PIN", "?")
        name = s.get("Tên", "?")
        phone = s.get("SĐT", "?")
        tg = "✅" if s.get("Telegram_ID") else "❌"
        txt += f"{i}. [{pin}] {name} - {phone} {tg}\n"
    
    await update.message.reply_text(txt, parse_mode="HTML")


# ==========================================
# /xoanv - Xóa nhân viên (Admin)
# ==========================================

async def xoanv_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xóa nhân viên (Admin only)"""
    user = update.effective_user
    args = context.args
    
    if str(user.id) != ADMIN_ID:
        await update.message.reply_text("❌ Chỉ Admin mới dùng được lệnh này!")
        return
    
    if not args:
        await update.message.reply_text(
            "📝 Cú pháp: /xoanv [PIN]\n"
            "Ví dụ: /xoanv 1234"
        )
        return
    
    pin = args[0]
    success, message = delete_staff(pin)
    
    if success:
        log_info(f"Admin xóa nhân viên PIN: {pin}")
    
    await update.message.reply_text(f"{'✅' if success else '❌'} {message}")


# ==========================================
# /top - Bảng xếp hạng
# ==========================================

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị bảng xếp hạng"""
    with get_db() as db:
        # Top theo Xu
        top_coin = db.query(Employee).order_by(Employee.coin.desc()).limit(10).all()
        
        txt = "🏆 <b>BẢNG XẾP HẠNG XU</b>\n"
        txt += "━━━━━━━━━━━━━━━━\n"
        
        medals = ["🥇", "🥈", "🥉"]
        for i, emp in enumerate(top_coin):
            medal = medals[i] if i < 3 else f"{i+1}."
            txt += f"{medal} {emp.name}: {emp.coin:,.0f} Xu\n"
        
        await update.message.reply_text(txt, parse_mode="HTML")


# ==========================================
# /thong_bao - Gửi thông báo (Admin)
# ==========================================

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gửi thông báo đến tất cả nhân viên (Admin only)"""
    user = update.effective_user
    
    if str(user.id) != ADMIN_ID:
        await update.message.reply_text("❌ Chỉ Admin mới dùng được lệnh này!")
        return
    
    if not context.args:
        await update.message.reply_text("📝 Cú pháp: /thong_bao [nội dung]")
        return
    
    message = " ".join(context.args)
    
    with get_db() as db:
        employees = db.query(Employee).all()
        sent = 0
        failed = 0
        
        for emp in employees:
            try:
                await context.bot.send_message(
                    chat_id=emp.telegram_id,
                    text=f"📢 <b>THÔNG BÁO</b>\n\n{message}",
                    parse_mode="HTML"
                )
                sent += 1
            except:
                failed += 1
        
        await update.message.reply_text(f"✅ Đã gửi: {sent}\n❌ Thất bại: {failed}")
