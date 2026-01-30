# --- FILE: handlers/order_handlers.py ---
# Xử lý order từ webapp

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from pydantic import BaseModel
from typing import List
from datetime import datetime

from config import MAIN_GROUP_ID, ORDER_TOPIC_ID, WEB_URL
from staff_sheet import get_staff_by_pin


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
# /order - Gọi menu order trong nhóm
# ==========================================

async def order_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hướng dẫn dùng App Order"""
    from config import WEB_URL
    
    msg = (
        "📱 <b>APP ORDER</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"👉 Truy cập: {WEB_URL}/order\n\n"
        "💡 Lưu trang này vào màn hình chính để dùng như app!"
    )
    await update.message.reply_text(msg, parse_mode="HTML")


# ==========================================
# API SUBMIT ORDER
# ==========================================

async def submit_order(order: OrderData, bot):
    """Xử lý submit order từ webapp"""
    try:
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
        
        msg = f"🔔 <b>{order.customer.upper()}</b> (từ {staff_name})\n"
        
        for item in order.items:
            extra = []
            if item.tops:
                extra.extend([t.name for t in item.tops])
            if item.notes:
                extra.extend(item.notes)
            
            detail = f" ({', '.join(extra)})" if extra else ""
            msg += f"• {item.qty}x <b>{item.name}</b>{detail}\n"
        
        await bot.send_message(
            chat_id=MAIN_GROUP_ID,
            message_thread_id=ORDER_TOPIC_ID,
            text=msg, 
            parse_mode="HTML"
        )
        
        # === THÊM ORDER VÀO PENDING LIST CHO KHI-POS ===
        try:
            # Import pending_pos_orders từ main
            import sys
            main_module = sys.modules.get('main') or sys.modules.get('__main__')
            if main_module and hasattr(main_module, 'pending_pos_orders'):
                pos_order = {
                    "order_id": order.order_id,
                    "customer": order.customer,
                    "staff_name": staff_name,
                    "staff_pin": order.staff_pin,
                    "items": [
                        {
                            "name": item.name,
                            "price": item.price,
                            "qty": item.qty,
                            "tops": [{"name": t.name, "price": t.price} for t in item.tops],
                            "notes": item.notes
                        }
                        for item in order.items
                    ],
                    "total": order.total,
                    "created_at": datetime.now().isoformat()
                }
                main_module.pending_pos_orders.append(pos_order)
                print(f"📤 Order {order.order_id} đã thêm vào pending list cho KHI-POS")
        except Exception as e:
            print(f"⚠️ Không thể thêm order vào pending list: {e}")
        
        return {"success": True, "message": "Đã gửi order thành công!"}
        
    except Exception as e:
        return {"success": False, "message": str(e)}


# ==========================================
# ORDER BUTTON CALLBACKS
# ==========================================

async def order_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý nút HỦY đơn"""
    query = update.callback_query
    user = query.from_user
    data = query.data
    
    if data.startswith("cancel_order_"):
        allowed_user_id = data.replace("cancel_order_", "")
        
        if str(user.id) != allowed_user_id:
            await query.answer()
            return
        
        try:
            await query.message.delete()
            await query.answer("✅ Đã hủy đơn!")
        except:
            await query.answer("⚠️ Không thể hủy đơn này!", show_alert=True)
