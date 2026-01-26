# --- FILE: handlers/order_handlers.py ---
# Xử lý order từ webapp

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from pydantic import BaseModel
from typing import List

from config import MAIN_GROUP_ID, ORDER_TOPIC_ID
from staff_sheet import get_staff_by_pin
from utils import log_order, log_error_with_context


# ==========================================
# MODELS
# ==========================================

class ToppingItem(BaseModel):
    name: str
    price: int = 0

class OrderItem(BaseModel):
    name: str
    price: int
    qty: int
    tops: List[ToppingItem] = []
    notes: List[str] = []

class OrderData(BaseModel):
    order_id: str
    customer: str
    staff_name: str
    staff_pin: str
    items: List[OrderItem]
    total: int


# ==========================================
# API SUBMIT ORDER
# ==========================================

async def submit_order(order: OrderData, bot):
    """Xử lý submit order từ webapp"""
    try:
        # Kiểm tra nhân viên đã đăng ký Telegram chưa
        staff = get_staff_by_pin(order.staff_pin)
        
        if not staff:
            return {"success": False, "message": "PIN không hợp lệ!"}
        
        staff_telegram_id = staff.get("Telegram_ID")
        
        if not staff_telegram_id:
            return {
                "success": False, 
                "message": f"Vui lòng đăng ký Telegram trước!\n\nMở bot và gửi:\n/dangky {order.staff_name} [SĐT của bạn]"
            }
        
        staff_name = staff.get("Tên")
        
        # Tạo nội dung tin nhắn
        msg = f"🔔 <b>ĐƠN: {order.customer.upper()}</b> (từ {staff_name})\n"
        
        for item in order.items:
            extra = []
            if item.tops:
                extra.extend([t.name for t in item.tops])
            if item.notes:
                extra.extend(item.notes)
            
            detail = f" ({', '.join(extra)})" if extra else ""
            msg += f"• {item.qty}x <b>{item.name}</b>{detail}\n"
        
        # Nút bấm
        kb = [
            [
                InlineKeyboardButton("❌ HỦY", callback_data=f"cancel_order_{staff_telegram_id}"),
                InlineKeyboardButton("✅ ĐÃ NHẬP MÁY", callback_data="pos_done")
            ]
        ]
        
        await bot.send_message(
            chat_id=MAIN_GROUP_ID,
            message_thread_id=ORDER_TOPIC_ID,
            text=msg, 
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="HTML"
        )
        
        # Log
        log_order(staff_name, order.customer, order.total, len(order.items))
        
        return {"success": True, "message": "Đã gửi order thành công!"}
        
    except Exception as e:
        log_error_with_context(e, "Submit order")
        return {"success": False, "message": str(e)}


# ==========================================
# ORDER BUTTON CALLBACKS
# ==========================================

async def order_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý nút HỦY và ĐÃ NHẬP MÁY"""
    query = update.callback_query
    user = query.from_user
    data = query.data
    
    if data.startswith("cancel_order_"):
        # Lấy telegram_id được phép hủy
        allowed_user_id = data.replace("cancel_order_", "")
        
        # Kiểm tra quyền
        if str(user.id) != allowed_user_id:
            await query.answer()  # Silent - không thông báo gì
            return
        
        # Xóa tin nhắn order
        try:
            await query.message.delete()
            await query.answer("✅ Đã hủy đơn!")
        except:
            await query.answer("⚠️ Không thể hủy đơn này!", show_alert=True)
    
    elif data == "pos_done":
        # Ai cũng có thể bấm "Đã nhập máy"
        try:
            # Sửa tin nhắn - xóa nút bấm
            old_text = query.message.text or query.message.caption or ""
            new_text = old_text + f"\n\n✅ Đã nhập máy"
            
            await query.edit_message_text(text=new_text, parse_mode="HTML")
            await query.answer("✅ Đã xác nhận!")
        except Exception as e:
            await query.answer(f"⚠️ Lỗi: {e}", show_alert=True)
