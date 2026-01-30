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
# PENDING ORDERS - Lưu trữ đơn chờ cho KHI-POS
# ==========================================
pending_pos_orders = []


# ==========================================
# MAPPING VIẾT TẮT
# ==========================================

PRODUCT_SHORT = {
    # Trà sữa
    "Trà Sữa Truyền Thống": "tt",
    "Trà Sữa Matcha": "mc",
    "Trà Sữa Caramel": "crm",
    "Trà Sữa Ô Long": "ts olong",
    "Trà Sữa Chocolate": "so",
    "Trà Sữa Đào": "ts đào",
    # Trà trái cây (bỏ chữ Trà)
    "Trà Đác Dâu Tằm": "đác dâu tằm",
    "Trà Đác Thơm": "đác thơm",
    "Trà Ổi Hồng": "ổi hồng",
    "Trà Nhiệt Đới": "nhiệt đới",
    "Trà Táo Xanh": "táo xanh",
    "Trà Dưa Lưới": "dưa lưới",
    "Trà Mãng Cầu": "mãng cầu",
    "Trà Cóc Hạt Đác": "cóc hạt đác",
    # Macchiato
    "Trà Đào Macchiato": "t.đào",
    "Trà Dâu Macchiato": "t.dâu",
    "Trà Vải Macchiato": "t.vải",
    "Hồng Trà Macchiato": "hồng trà",
    "Ô Long Macchiato": "t.olong",
    "Trà Sen Macchiato": "t.sen",
    # Đặc biệt
    "Trà Sủi": "trà sủi",
    "Sữa Tươi Trân Châu Đ.Đ": "st",
    "Hồng Trà Latte": "hồng trà latte",
    "Matcha Latte": "matcha latte",
    # Ko Topping
    "TS Truyền Thống Ko Topping": "tt ko top",
    "TS Matcha Ko Topping": "mc ko top",
    "TS Caramel Ko Topping": "crm ko top",
    "TS Ô Long Ko Topping": "ts olong ko top",
    "TS Chocolate Ko Topping": "so ko top",
    "TS Đào Ko Topping": "ts đào ko top",
    "Trà Đào Ko Topping": "t.đào ko top",
    "Trà Dâu Ko Topping": "t.dâu ko top",
    "Trà Vải Ko Topping": "t.vải ko top",
    "Hồng Trà Ko Topping": "hồng trà ko top",
    "Ô Long Ko Topping": "t.olong ko top",
    "Trà Sen Ko Topping": "t.sen ko top",
    "Trà Sủi Ko Topping": "trà sủi ko top",
    "Hồng Trà Latte Ko Topping": "hồng trà latte ko top",
    "Matcha Latte Ko Topping": "matcha latte ko top",
    "Trà Đác Dâu Tằm Ko Topping": "đác dâu tằm ko top",
    "Trà Đác Thơm Ko Topping": "đác thơm ko top",
    "Trà Ổi Hồng Ko Topping": "ổi hồng ko top",
    "Trà Nhiệt Đới Ko Topping": "nhiệt đới ko top",
    "Trà Táo Xanh Ko Topping": "táo xanh ko top",
    "Trà Dưa Lưới Ko Topping": "dưa lưới ko top",
    "Trà Mãng Cầu Ko Topping": "mãng cầu ko top",
    "Trà Cóc Hạt Đác Ko Topping": "cóc hạt đác ko top",
    # Topping thêm
    "Thêm Trân Châu": "+tc",
    "Thêm Củ Năng": "+cn",
    "Thêm Phô Mai": "+pm",
    "Thêm Rau Câu": "+rc",
    "Thêm Khúc Bạch": "+kb",
    "Thêm Sương Sáo": "+ss",
    "Thêm Thạch Đào": "+thạch đào",
    "Thêm Flan Trứng": "+flan",
    "Thêm Ngọc Trai": "+nt",
    "Thêm Khoai Dẻo": "+kd",
    "Thêm Đác Thơm": "+đác thơm",
    "Thêm Đác Dâu Tằm": "+đác dâu tằm",
    "Thêm Trái Cây Nhiệt Đới": "+trái cây nhiệt đới",
    "Thêm Táo Xanh": "+táo xanh",
    "Thêm Dưa Lưới": "+dưa lưới",
    "Thêm Ổi Hồng": "+ổi hồng",
    "Thêm Mãng Cầu": "+mãng cầu",
}

TOPPING_SHORT = {
    # Topping cơ bản
    "Trân Châu": "tc",
    "Củ Năng": "cn",
    "Phô Mai": "pm",
    "Rau Câu": "rc",
    "Khúc Bạch": "kb",
    "Sương Sáo": "ss",
    "Thạch Đào": "thạch đào",
    "Flan Trứng": "flan",
    "Ngọc Trai": "nt",
    "Khoai Dẻo": "kd",
    # Topping trái cây - giữ nguyên
    "Đác Thơm": "đác thơm",
    "Đác Dâu Tằm": "đác dâu tằm",
    "Trái Cây Nhiệt Đới": "trái cây nhiệt đới",
    "Táo Xanh": "táo xanh",
    "Dưa Lưới": "dưa lưới",
    "Ổi Hồng": "ổi hồng",
    "Mãng Cầu": "mãng cầu",
}

def shorten_product(name):
    """Rút gọn tên sản phẩm"""
    return PRODUCT_SHORT.get(name, name.lower())

def shorten_topping(topping_name):
    """Rút gọn tên topping trong ghi chú (Không X, Bù Y)"""
    # Xử lý "Không X"
    if topping_name.startswith("Không "):
        top = topping_name.replace("Không ", "")
        short = TOPPING_SHORT.get(top, top.lower())
        return f"ko {short}"
    # Xử lý "Bù X"
    elif topping_name.startswith("Bù "):
        top = topping_name.replace("Bù ", "")
        short = TOPPING_SHORT.get(top, top.lower())
        return f"bù {short}"
    # Topping thường (chỉ chọn)
    else:
        return TOPPING_SHORT.get(topping_name, topping_name.lower())

def format_order_item(item):
    """Format 1 item order thành dạng rút gọn"""
    # Rút gọn tên món
    name_short = shorten_product(item.name)
    
    # Xử lý topping và ghi chú
    details = []
    
    # Gom nhóm "ko" và "bù" lại với nhau
    ko_list = []
    bu_list = []
    other_tops = []
    
    if item.tops:
        for t in item.tops:
            short = shorten_topping(t.name)
            if short.startswith("ko "):
                ko_list.append(short.replace("ko ", ""))
            elif short.startswith("bù "):
                bu_list.append(short.replace("bù ", ""))
            else:
                other_tops.append(short)
    
    # Ghép "ko" và "bù" thành 1 chuỗi
    if ko_list:
        if bu_list:
            # Có bù: ko rc, cn bù kd
            details.append(f"ko {', '.join(ko_list)} bù {', '.join(bu_list)}")
        else:
            # Chỉ ko: ko rc, cn, kd
            details.append(f"ko {', '.join(ko_list)}")
    elif bu_list:
        details.append(f"bù {', '.join(bu_list)}")
    
    # Thêm topping thường (chỉ chọn)
    if other_tops:
        details.extend(other_tops)
    
    # Thêm ghi chú (viết thường)
    if item.notes:
        details.extend([n.lower() for n in item.notes])
    
    # Ghép lại
    if details:
        return f"{item.qty}x {name_short} ({', '.join(details)})"
    else:
        return f"{item.qty}x {name_short}"


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
    global pending_pos_orders
    
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
        
        # === FORMAT TIN NHẮN RÚT GỌN ===
        msg = f"🔔 <b>{order.customer.upper()}</b>\n"
        
        for item in order.items:
            item_text = format_order_item(item)
            msg += f"• {item_text}\n"
        
        await bot.send_message(
            chat_id=MAIN_GROUP_ID,
            message_thread_id=ORDER_TOPIC_ID,
            text=msg, 
            parse_mode="HTML"
        )
        
        # === THÊM ORDER VÀO PENDING LIST CHO KHI-POS ===
        pos_order = {
            "order_id": order.order_id,
            "customer": order.customer,
            "staff_name": staff_name,
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
        pending_pos_orders.append(pos_order)
        print(f"📤 Order {order.order_id} đã thêm vào pending list ({len(pending_pos_orders)} đơn chờ)")
        
        return {"success": True, "message": "Đã gửi order thành công!"}
        
    except Exception as e:
        print(f"❌ Lỗi submit order: {e}")
        return {"success": False, "message": str(e)}


# ==========================================
# HÀM LẤY VÀ XÓA PENDING ORDERS
# ==========================================

def get_pending_orders_list():
    """Trả về danh sách order đang chờ"""
    global pending_pos_orders
    return pending_pos_orders


def remove_pending_order(order_id: str):
    """Xóa order khỏi pending list khi POS đã nhận"""
    global pending_pos_orders
    before = len(pending_pos_orders)
    pending_pos_orders = [o for o in pending_pos_orders if o.get("order_id") != order_id]
    after = len(pending_pos_orders)
    print(f"✅ Xóa order {order_id}: {before} -> {after} đơn")


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
