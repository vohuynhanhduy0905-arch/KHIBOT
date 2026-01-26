# --- FILE: handlers/admin_handlers.py ---
# Xử lý các lệnh admin: /dangky, /dsnv, /xoanv, /thong_bao

from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_ID, WEB_URL
from database import SessionLocal, Employee
from staff_sheet import register_staff, delete_staff, get_all_staff
from handlers.user_handlers import check_private


# ==========================================
# /dangky - Đăng ký nhân viên (FORMAT ĐẸP)
# ==========================================

async def dangky_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Đăng ký nhân viên mới"""
    if not await check_private(update, context): 
        return
    
    user = update.effective_user
    text = update.message.text.strip()
    
    parts = text.split(maxsplit=2)
    if len(parts) < 3:
        await update.message.reply_text(
            "📝 <b>ĐĂNG KÝ NHÂN VIÊN ORDER</b>\n\n"
            "Cú pháp: <code>/dangky Tên SĐT</code>\n\n"
            "Ví dụ: <code>/dangky Anh_Duy 0867760667</code>\n\n"
            "⚠️ Lưu ý:\n"
            "• Tên không có dấu cách (dùng _ nếu cần)\n"
            "• SĐT phải là số điện thoại hợp lệ",
            parse_mode="HTML"
        )
        return
    
    name = parts[1]
    phone = parts[2]
    
    if not phone.isdigit() or len(phone) < 9:
        await update.message.reply_text("❌ SĐT không hợp lệ! Vui lòng nhập số điện thoại đúng.")
        return
    
    success, message, pin = register_staff(name, phone, str(user.id))
    
    if success:
        await update.message.reply_text(
            f"✅ <b>{message}</b>\n\n"
            f"👤 Tên: {name}\n"
            f"📱 SĐT: {phone}\n"
            f"🔑 Mã PIN: <code>{pin}</code>\n\n"
            f"📲 Dùng mã PIN này để đăng nhập webapp order.\n"
            f"🔗 Link: {WEB_URL}/order",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(f"❌ {message}")


# ==========================================
# /dsnv - Danh sách nhân viên (Admin)
# ==========================================

async def dsnv_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xem danh sách nhân viên (Admin only)"""
    if str(update.effective_user.id) != ADMIN_ID:
        return
    
    staff_list = get_all_staff()
    
    if not staff_list:
        await update.message.reply_text("📋 Chưa có nhân viên nào đăng ký.")
        return
    
    msg = "📋 <b>DANH SÁCH NHÂN VIÊN</b>\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"
    
    for i, s in enumerate(staff_list, 1):
        tg_status = "✅" if s.get("Telegram_ID") else "❌"
        msg += f"{i}. <b>{s.get('Tên')}</b>\n"
        msg += f"   PIN: <code>{s.get('PIN')}</code> | SĐT: {s.get('SĐT')} {tg_status}\n"
    
    msg += f"\n📊 Tổng: {len(staff_list)} nhân viên"
    
    await update.message.reply_text(msg, parse_mode="HTML")


# ==========================================
# /xoanv - Xóa nhân viên (Admin)
# ==========================================

async def xoanv_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xóa nhân viên (Admin only)"""
    if str(update.effective_user.id) != ADMIN_ID:
        return
    
    if not context.args:
        await update.message.reply_text(
            "Cú pháp: <code>/xoanv [PIN]</code>\n"
            "Ví dụ: <code>/xoanv 1234</code>",
            parse_mode="HTML"
        )
        return
    
    pin = context.args[0]
    success, message = delete_staff(pin)
    
    await update.message.reply_text(f"{'✅' if success else '❌'} {message}")


# ==========================================
# /thong_bao - Gửi thông báo (Admin)
# ==========================================

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gửi thông báo đến tất cả nhân viên (Admin only)"""
    if str(update.effective_user.id) != ADMIN_ID:
        return
    
    if not context.args:
        await update.message.reply_text("📝 Cú pháp: /thong_bao [nội dung]")
        return
    
    message = " ".join(context.args)
    
    db = SessionLocal()
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
    
    db.close()
    await update.message.reply_text(f"✅ Đã gửi: {sent}\n❌ Thất bại: {failed}")
