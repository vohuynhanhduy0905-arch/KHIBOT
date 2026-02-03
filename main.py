# --- FILE: main.py ---
# Bot Trà Sữa Khỉ - Phiên bản tối ưu với modules
# ĐÃ CẬP NHẬT: Giới hạn game Tài Xỉu

import asyncio
import random
from datetime import datetime, timedelta, date
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from telegram import (
    Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, 
    MenuButtonCommands
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, 
    ContextTypes, CallbackQueryHandler, MessageReactionHandler
)
from sqlalchemy.sql import func

from config import (
    TOKEN, MAIN_GROUP_ID, WEB_URL, ORDER_TOPIC_ID, CHAT_TOPIC_ID, MAPS_URL,
    MORNING_MESSAGES, EVENING_MESSAGES,
    TX_WIN_RATE, TX_MAX_PLAYS_PER_DAY, TX_MAX_BET_PER_DAY  # MỚI
)
from database import init_db, SessionLocal, Employee, Review, ShopLog, MenuCategory, MenuProduct, MenuTopping, MenuQuickNote
from staff_sheet import get_staff_by_pin, get_all_staff

from handlers import (
    start_command, me_command, qr_command, top_command,
    daily_command, gift_command, shop_command,
    get_main_menu, check_private,
    dangky_command, dsnv_command, xoanv_command, broadcast_command,
    game_ui_command, kbb_command,
    handle_kbb_create, handle_kbb_join, handle_kbb_choose,
    handle_pk_create, handle_pk_join,
    order_command, submit_order, OrderData,
    pending_pos_orders, get_pending_orders_list, remove_pending_order
)

init_db()
# === ĐỒNG BỘ EMOJI TỪ SHEET KHI KHỞI ĐỘNG ===
def sync_emoji_from_sheet():
    """Đồng bộ emoji từ Google Sheet về Database 1 lần khi khởi động"""
    try:
        print("🔄 Đang đồng bộ emoji từ Google Sheet...")
        sheet_data = get_all_staff()
        
        db = SessionLocal()
        updated = 0
        
        for staff in sheet_data:
            tg_id = str(staff.get("Telegram_ID", "")).strip()
            sheet_emoji = str(staff.get("Emoji", "")).strip()
            
            if tg_id and sheet_emoji:
                emp = db.query(Employee).filter(Employee.telegram_id == tg_id).first()
                if emp and emp.emoji != sheet_emoji:
                    emp.emoji = sheet_emoji
                    updated += 1
        
        db.commit()
        db.close()
        print(f"✅ Đồng bộ emoji hoàn tất! Cập nhật {updated} nhân viên.")
    except Exception as e:
        print(f"⚠️ Lỗi đồng bộ emoji: {e}")

# Chạy đồng bộ khi khởi động
sync_emoji_from_sheet()
templates = Jinja2Templates(directory="templates")
bot_app = Application.builder().token(TOKEN).build()

# Lưu tin nhắn thông báo: {message_id: set(user_ids đã nhận Xu)}
DAILY_ANNOUNCEMENT_MSG = {}

# Reward cho reaction
REACTION_REWARD = 10000


# ==========================================
# HÀM KIỂM TRA GIỚI HẠN TÀI XỈU (MỚI)
# ==========================================

def check_tx_limit(emp: Employee, bet_amount: int) -> tuple[bool, str]:
    """
    Kiểm tra giới hạn chơi Tài Xỉu
    Returns: (can_play: bool, error_message: str)
    """
    today = date.today()
    
    # Reset nếu là ngày mới
    if emp.tx_last_date != today:
        emp.tx_last_date = today
        emp.tx_play_count = 0
        emp.tx_total_bet = 0
    
    # Kiểm tra số lần chơi
    if emp.tx_play_count >= TX_MAX_PLAYS_PER_DAY:
        return False, f"⚠️ Bạn đã chơi {TX_MAX_PLAYS_PER_DAY} lần hôm nay!\n📅 Quay lại vào ngày mai nhé."
    
    # Kiểm tra tổng tiền cược
    if emp.tx_total_bet + bet_amount > TX_MAX_BET_PER_DAY:
        remaining = TX_MAX_BET_PER_DAY - emp.tx_total_bet
        if remaining <= 0:
            return False, f"⚠️ Bạn đã cược hết {TX_MAX_BET_PER_DAY:,.0f} Xu hôm nay!\n📅 Quay lại vào ngày mai nhé."
        else:
            return False, f"⚠️ Bạn chỉ còn được cược {remaining:,.0f} Xu hôm nay!\n💡 Chọn mức cược nhỏ hơn."
    
    return True, ""


def get_tx_status(emp: Employee) -> str:
    """Lấy thông tin giới hạn hiện tại của user"""
    today = date.today()
    
    # Reset nếu là ngày mới
    if emp.tx_last_date != today:
        plays_left = TX_MAX_PLAYS_PER_DAY
        bet_left = TX_MAX_BET_PER_DAY
    else:
        plays_left = TX_MAX_PLAYS_PER_DAY - (emp.tx_play_count or 0)
        bet_left = TX_MAX_BET_PER_DAY - (emp.tx_total_bet or 0)
    
    return (
        f"📊 <b>Hạn mức hôm nay:</b>\n"
        f"🎮 Còn {plays_left}/{TX_MAX_PLAYS_PER_DAY} lượt chơi\n"
        f"💰 Còn {bet_left:,.0f}/{TX_MAX_BET_PER_DAY:,.0f} Xu cược"
    )


# ==========================================
# XỬ LÝ REACTION (THẢ TIM NHẬN XU)
# ==========================================

async def handle_reaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi có người thả reaction vào tin nhắn"""
    try:
        reaction = update.message_reaction
        
        if not reaction:
            return
        
        message_id = reaction.message_id
        user = reaction.user
        chat_id = reaction.chat.id
        
        # Chỉ xử lý trong group chính
        if chat_id != MAIN_GROUP_ID:
            return
        
        # Kiểm tra tin nhắn có phải thông báo không
        if message_id not in DAILY_ANNOUNCEMENT_MSG:
            return
        
        user_id = user.id
        
        # Kiểm tra user đã nhận Xu cho tin nhắn này chưa
        if user_id in DAILY_ANNOUNCEMENT_MSG[message_id]:
            return
        
        # Kiểm tra có phải reaction ❤️ không
        new_reactions = reaction.new_reaction
        has_heart = False
        
        for r in new_reactions:
            # ReactionTypeEmoji có attribute emoji
            if hasattr(r, 'emoji') and r.emoji == "❤":
                has_heart = True
                break
        
        if not has_heart:
            return
        
        # Cộng Xu cho user
        db = SessionLocal()
        emp = db.query(Employee).filter(Employee.telegram_id == str(user_id)).first()
        
        if emp:
            emp.coin += REACTION_REWARD
            db.commit()
            
            # Đánh dấu đã nhận
            DAILY_ANNOUNCEMENT_MSG[message_id].add(user_id)
            
            # Gửi thông báo riêng
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"❤️ <b>CẢM ƠN BẠN ĐÃ THẢ TIM!</b>\n"
                        f"━━━━━━━━━━━━━━━━\n"
                        f"🎁 +{REACTION_REWARD:,.0f} Xu\n"
                        f"🪙 Xu hiện có: <b>{emp.coin:,.0f}</b>\n"
                        f"━━━━━━━━━━━━━━━━\n"
                        f"💪 Chúc bạn ngày làm việc vui vẻ!"
                    ),
                    parse_mode="HTML"
                )
            except:
                pass  # User có thể đã block bot
            
            print(f"❤️ {emp.name} thả tim → +{REACTION_REWARD:,} Xu")
        
        db.close()
        
    except Exception as e:
        print(f"❌ Lỗi xử lý reaction: {e}")

async def handle_game_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data
    chat_type = query.message.chat.type
    
    try:
        await query.answer()
    except:
        pass
    
    if data == "close_menu":
        await query.message.delete()
        return
    
    if data == "back_home":
        msg = f"🎰 <b>TRUNG TÂM GIẢI TRÍ</b> 🎰\nChào <b>{user.full_name}</b>, đại gia muốn chơi gì?"
        keyboard = [
            [InlineKeyboardButton("🎲 Tài Xỉu", callback_data="menu_tx")],
            [InlineKeyboardButton("🥊 PK Xúc Xắc", callback_data="menu_pk"), InlineKeyboardButton("✂️ Kéo Búa Bao", callback_data="kbb_menu")],
            [InlineKeyboardButton("❌ Đóng", callback_data="close_menu")]
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return
    
    # ==========================================
    # MENU TÀI XỈU (ĐÃ CẬP NHẬT)
    # ==========================================
    if data == "menu_tx":
        if chat_type != "private":
            await query.answer("🎲 Vào chat riêng với Bot để chơi!", show_alert=True)
            return
        
        # Lấy thông tin giới hạn của user
        db = SessionLocal()
        emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
        
        if emp:
            status = get_tx_status(emp)
        else:
            status = ""
        db.close()
        
        # Cập nhật tỷ lệ ăn mới
        win_percent = int(TX_WIN_RATE * 100)
        txt = (
            f"🎲 <b>TÀI XỈU SIÊU TỐC</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"🔴 <b>XỈU:</b> 3 - 10 điểm\n"
            f"🔵 <b>TÀI:</b> 11 - 18 điểm\n"
            f"⚡ <b>Tỉ lệ ăn:</b> 1 ăn {TX_WIN_RATE}\n"
            f"⚠️ <b>Bão (3 số giống nhau):</b> Nhà cái ăn hết!\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"{status}"
        )
        kb = [
            [InlineKeyboardButton("🔴 Đặt XỈU", callback_data="tx_chon_xiu"), InlineKeyboardButton("🔵 Đặt TÀI", callback_data="tx_chon_tai")],
            [InlineKeyboardButton("🔙 Quay lại", callback_data="back_home")]
        ]
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return
    
    if data == "menu_pk":
        txt = "🥊 <b>SÀN ĐẤU PK 1vs1 (XU)</b>\nChọn mức cược tại đây, Bot sẽ gửi lời mời vào Nhóm chung.\n👇 <b>Chọn mức thách đấu:</b>"
        kb = [[InlineKeyboardButton("⚡ 10k Xu", callback_data="pk_create_10000"), InlineKeyboardButton("⚡ 20k Xu", callback_data="pk_create_20000"), InlineKeyboardButton("⚡ 50k Xu", callback_data="pk_create_50000"), InlineKeyboardButton("⚡ 100k Xu", callback_data="pk_create_100000")], [InlineKeyboardButton("🔙 Quay lại", callback_data="back_home")]]
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return
    
    if data == "kbb_menu":
        if chat_type != "private":
            await query.answer("✂️ Vào chat riêng với Bot để chơi!", show_alert=True)
            return
        txt = "✂️ <b>KÉO BÚA BAO</b> ✊\n━━━━━━━━━━━━━━━━\nTạo kèo thách đấu, chờ người nhận!\nCả 2 chọn bí mật, reveal cùng lúc.\n━━━━━━━━━━━━━━━━\n🪙 Chọn mức cược:"
        kb = [[InlineKeyboardButton("10k Xu", callback_data="kbb_create_10000"), InlineKeyboardButton("20k Xu", callback_data="kbb_create_20000")], [InlineKeyboardButton("50k Xu", callback_data="kbb_create_50000"), InlineKeyboardButton("100k Xu", callback_data="kbb_create_100000")], [InlineKeyboardButton("🔙 Quay lại", callback_data="back_home")]]
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return
    
    if data in ["tx_chon_xiu", "tx_chon_tai"]:
        choice = "xiu" if data == "tx_chon_xiu" else "tai"
        txt = f"{'🔴 XỈU' if choice == 'xiu' else '🔵 TÀI'} - Chọn mức cược:"
        kb = [[InlineKeyboardButton("5k", callback_data=f"tx_bet_{choice}_5000"), InlineKeyboardButton("10k", callback_data=f"tx_bet_{choice}_10000"), InlineKeyboardButton("20k", callback_data=f"tx_bet_{choice}_20000"), InlineKeyboardButton("50k", callback_data=f"tx_bet_{choice}_50000")], [InlineKeyboardButton("🔙 Quay lại", callback_data="menu_tx")]]
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return
    
    # ==========================================
    # XỬ LÝ ĐẶT CƯỢC TÀI XỈU (ĐÃ CẬP NHẬT)
    # ==========================================
    if data.startswith("tx_bet_"):
        parts = data.split("_")
        choice, amount = parts[2], int(parts[3])
        
        db = SessionLocal()
        emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
        
        if not emp:
            await query.answer("❌ Bạn chưa đăng ký!", show_alert=True)
            db.close()
            return
        
        if emp.coin < amount:
            await query.answer("💸 Không đủ Xu!", show_alert=True)
            db.close()
            return
        
        # === KIỂM TRA GIỚI HẠN (MỚI) ===
        can_play, error_msg = check_tx_limit(emp, amount)
        if not can_play:
            await query.answer(error_msg, show_alert=True)
            db.close()
            return
        
        # Trừ tiền cược
        emp.coin -= amount
        
        # Cập nhật tracking (MỚI)
        today = date.today()
        if emp.tx_last_date != today:
            emp.tx_last_date = today
            emp.tx_play_count = 1
            emp.tx_total_bet = amount
        else:
            emp.tx_play_count = (emp.tx_play_count or 0) + 1
            emp.tx_total_bet = (emp.tx_total_bet or 0) + amount
        
        db.commit()
        db.close()
        
        try:
            await query.message.delete()
        except:
            pass
        
        # Tung xúc xắc
        dice_msg = await context.bot.send_dice(chat_id=user.id, emoji="🎲")
        dice1 = dice_msg.dice.value
        await asyncio.sleep(1)
        
        dice_msg2 = await context.bot.send_dice(chat_id=user.id, emoji="🎲")
        dice2 = dice_msg2.dice.value
        await asyncio.sleep(1)
        
        dice_msg3 = await context.bot.send_dice(chat_id=user.id, emoji="🎲")
        dice3 = dice_msg3.dice.value
        await asyncio.sleep(2)
        
        total = dice1 + dice2 + dice3
        is_bao = (dice1 == dice2 == dice3)
        result_is_xiu = total <= 10
        winnings = 0
        
        if is_bao:
            result = "💥 BÃO! Nhà cái ăn hết!"
        elif (choice == "xiu" and result_is_xiu) or (choice == "tai" and not result_is_xiu):
            # === TỶ LỆ ĂN MỚI ===
            winnings = int(amount * (1 + TX_WIN_RATE))  # 1 + 0.80 = 1.80
            result = f"🎉 THẮNG! +{winnings - amount:,.0f} Xu"
        else:
            result = f"😢 THUA! -{amount:,.0f} Xu"
        
        db = SessionLocal()
        emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
        if winnings > 0:
            emp.coin += winnings
        db.commit()
        final_coin = emp.coin
        
        # Lấy thông tin còn lại
        plays_left = TX_MAX_PLAYS_PER_DAY - (emp.tx_play_count or 0)
        bet_left = TX_MAX_BET_PER_DAY - (emp.tx_total_bet or 0)
        db.close()
        
        result_type = "XỈU" if result_is_xiu else "TÀI"
        msg = (
            f"🎲 <b>KẾT QUẢ TÀI XỈU</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"🎯 Bạn đặt: {'🔴 XỈU' if choice == 'xiu' else '🔵 TÀI'}\n"
            f"🎲 Kết quả: {dice1} + {dice2} + {dice3} = {total} ({result_type})\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"{result}\n"
            f"🪙 Xu hiện có: <b>{final_coin:,.0f}</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"📊 Còn {plays_left} lượt | {bet_left:,.0f} Xu cược"
        )
        kb = [[InlineKeyboardButton("🔄 Chơi tiếp", callback_data="menu_tx"), InlineKeyboardButton("🔙 Menu Game", callback_data="back_home")]]
        await context.bot.send_message(chat_id=user.id, text=msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return
    
    if data.startswith("buy_salary_"):
        vnd_amount = int(data.split("_")[-1])
        cost_xu = vnd_amount * 100
        db = SessionLocal()
        emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
        if not emp:
            db.close()
            return
        if emp.coin >= cost_xu:
            emp.coin -= cost_xu
            emp.balance += vnd_amount
            log_entry = ShopLog(staff_id=str(user.id), item_name=f"Quy đổi {vnd_amount}đ Lương", cost=cost_xu, status="done")
            db.add(log_entry)
            db.commit()
            await query.edit_message_text(f"✅ <b>ĐỔI THÀNH CÔNG!</b>\n\n💸 -{cost_xu:,.0f} Xu\n💵 +{vnd_amount:,.0f}đ Lương\n\n🪙 Xu còn: {emp.coin:,.0f}\n💰 Lương: {emp.balance:,.0f}đ", parse_mode="HTML")
        else:
            await query.answer(f"❌ Không đủ Xu! Cần {cost_xu:,.0f} Xu", show_alert=True)
        db.close()

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from config import ADMIN_ID
    from telegram import ReplyKeyboardRemove
    
    text = update.message.text
    user_id = str(update.effective_user.id)
    
    # Menu nhân viên
    if text == "💳 Ví & Thẻ":
        await me_command(update, context)
    elif text == "📅 Điểm Danh":
        await daily_command(update, context)
    elif text == "🎰 Giải Trí":
        await game_ui_command(update, context)
    elif text == "🛒 Shop Xu":
        await shop_command(update, context)
    elif text == "🏆 BXH Đại Gia":
        await top_command(update, context)
    elif text == "🚀 Lấy mã QR":
        await qr_command(update, context)
    
    # Menu Admin (chỉ admin)
    elif user_id == ADMIN_ID:
        admin_buttons = ["📋 Danh Sách NV", "📢 Gửi Thông Báo", "🔄 Reset Toàn Bộ", "❌ Thoát Admin", "📝 Xem Kho Review", "🗑 Xóa Hết Review"]
        
        if text in admin_buttons:
            db = SessionLocal()
            
            if text == "📋 Danh Sách NV":
                emps = db.query(Employee).all()
                if not emps:
                    msg = "Chưa có nhân viên nào."
                else:
                    msg = "📋 <b>QUẢN LÝ NHÂN VIÊN</b>\n"
                    for e in emps:
                        msg += (
                            f"➖➖➖➖➖➖➖➖\n"
                            f"👤 <b>{e.name}</b> ({e.emoji})\n"
                            f"💰 Lương: {e.balance:,.0f}đ | 🪙 Xu: {e.coin:,.0f}\n"
                            f"👉 Lương: /tip_{e.telegram_id} | /fine_{e.telegram_id}\n"
                            f"👉 Xu: /tipxu_{e.telegram_id} | /finex_{e.telegram_id}\n"
                            f"🗑 Xóa: /del_{e.telegram_id}\n"
                        )
                if len(msg) > 4000:
                    msg = msg[:4000] + "\n...(Danh sách quá dài)"
                await update.message.reply_text(msg, parse_mode="HTML")
            
            elif text == "📝 Xem Kho Review":
                reviews = db.query(Review).all()
                msg = "📝 <b>KHO REVIEW:</b>\n" + "\n".join([f"- {r.content}" for r in reviews]) if reviews else "📭 Kho review trống."
                if len(msg) > 4000:
                    msg = msg[:4000] + "..."
                await update.message.reply_text(msg, parse_mode="HTML")
            
            elif text == "🗑 Xóa Hết Review":
                db.query(Review).delete()
                db.commit()
                await update.message.reply_text("🗑 Đã xóa sạch kho review.")
            
            elif text == "🔄 Reset Toàn Bộ":
                db.query(Employee).update({Employee.balance: 0})
                db.commit()
                await update.message.reply_text("✅ Đã reset ví lương về 0 cho tất cả.")
            
            elif text == "📢 Gửi Thông Báo":
                await update.message.reply_text("⚠️ Gõ: `/thong_bao Nội dung`", parse_mode="Markdown")
            
            elif text == "❌ Thoát Admin":
                await update.message.reply_text("🔒 Đã thoát Admin.", reply_markup=ReplyKeyboardRemove())
            
            db.close()
        else:
            # Nếu admin gõ text khác -> thêm review
            await handle_add_review(update, context)

async def run_announcement_scheduler():
    import pytz
    vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    while True:
        now = datetime.now(vn_tz)
        next_8am = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if now.hour >= 8:
            next_8am += timedelta(days=1)
        next_5pm = now.replace(hour=17, minute=0, second=0, microsecond=0)
        if now.hour >= 17:
            next_5pm += timedelta(days=1)
        if next_8am < next_5pm:
            wait_seconds = (next_8am - now).total_seconds()
            is_morning = True
        else:
            wait_seconds = (next_5pm - now).total_seconds()
            is_morning = False
        print(f"⏰ Chờ {wait_seconds/3600:.1f}h để gửi thông báo {'sáng' if is_morning else 'chiều'}")
        await asyncio.sleep(wait_seconds)
        messages = MORNING_MESSAGES if is_morning else EVENING_MESSAGES
        text = random.choice(messages)
        
        # Thêm hướng dẫn thả tim
        text += f"\n\n❤️ <b>Thả tim để nhận {REACTION_REWARD:,.0f} Xu!</b>"
        
        try:
            sent_msg = await bot_app.bot.send_message(chat_id=MAIN_GROUP_ID, message_thread_id=CHAT_TOPIC_ID, text=text, parse_mode="HTML")
            
            # Lưu message_id để track reaction
            DAILY_ANNOUNCEMENT_MSG[sent_msg.message_id] = set()
            
            print(f"✅ Đã gửi thông báo {'sáng' if is_morning else 'chiều'} (msg_id: {sent_msg.message_id})")
        except Exception as e:
            print(f"❌ Lỗi gửi thông báo: {e}")
        await asyncio.sleep(60)

# HANDLERS
bot_app.add_handler(CommandHandler("start", start_command))
bot_app.add_handler(CommandHandler("me", me_command))
bot_app.add_handler(CommandHandler("qr", qr_command))
bot_app.add_handler(CommandHandler("top", top_command))
bot_app.add_handler(CommandHandler("game", game_ui_command))
bot_app.add_handler(CommandHandler("tx", game_ui_command))
bot_app.add_handler(CommandHandler("pk", game_ui_command))
bot_app.add_handler(CommandHandler("diemdanh", daily_command))
bot_app.add_handler(CommandHandler("gift", gift_command))
bot_app.add_handler(CommandHandler("qua", gift_command))
bot_app.add_handler(CommandHandler("shop", shop_command))
bot_app.add_handler(CommandHandler("kbb", kbb_command))
bot_app.add_handler(CommandHandler("order", order_command))
bot_app.add_handler(CommandHandler("dangky", dangky_command))
bot_app.add_handler(CommandHandler("dsnv", dsnv_command))
bot_app.add_handler(CommandHandler("xoanv", xoanv_command))
bot_app.add_handler(CommandHandler("thong_bao", broadcast_command))

# ==========================================
# ADMIN SYSTEM
# ==========================================

async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu Admin với keyboard"""
    from config import ADMIN_ID
    from telegram import ReplyKeyboardMarkup
    
    if str(update.effective_user.id) != ADMIN_ID:
        return
    
    keyboard = [
        ["📋 Danh Sách NV", "📢 Gửi Thông Báo"],
        ["📝 Xem Kho Review", "🗑 Xóa Hết Review"],
        ["🔄 Reset Toàn Bộ", "❌ Thoát Admin"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("🔓 <b>MENU ADMIN</b>", reply_markup=reply_markup, parse_mode="HTML")

async def handle_add_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Thêm review vào kho"""
    from config import ADMIN_ID
    if str(update.effective_user.id) != ADMIN_ID:
        return
    
    text = update.message.text
    if not text:
        return
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    db = SessionLocal()
    count = 0
    try:
        for content in lines:
            db.add(Review(content=content))
            count += 1
        db.commit()
        await update.message.reply_text(f"✅ Đã thêm {count} câu review.")
    except:
        pass
    db.close()

async def quick_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý các lệnh nhanh: /tip_, /fine_, /tipxu_, /finex_, /del_"""
    from config import ADMIN_ID
    if str(update.effective_user.id) != ADMIN_ID:
        return
    
    command = update.message.text
    try:
        action_part, target_id = command[1:].split('_', 1)
    except:
        return
    
    db = SessionLocal()
    emp = db.query(Employee).filter(Employee.telegram_id == target_id).first()
    
    if emp:
        if action_part == "tip":
            emp.balance += 5000
            db.commit()
            await update.message.reply_text(f"✅ Thưởng nóng 5k lương cho {emp.name}.")
        elif action_part == "fine":
            emp.balance -= 5000
            db.commit()
            await update.message.reply_text(f"🚫 Phạt 5k lương của {emp.name}.")
        elif action_part == "tipxu":
            emp.coin += 50000
            db.commit()
            await update.message.reply_text(f"✅ Buff 50k Xu cho {emp.name}.")
        elif action_part == "finex":
            emp.coin -= 50000
            db.commit()
            await update.message.reply_text(f"🚫 Tịch thu 50k Xu của {emp.name}.")
        elif action_part == "del":
            name = emp.name
            db.delete(emp)
            db.commit()
            await update.message.reply_text(f"🗑 Đã xóa nhân viên {name}.")
    
    db.close()

bot_app.add_handler(CommandHandler("admin", admin_dashboard))
bot_app.add_handler(MessageHandler(filters.Regex(r'^/(tip|fine|tipxu|finex|del)_\d+$'), quick_action_handler))

# Lệnh test gửi thông báo (chỉ admin)
async def test_announcement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin test gửi thông báo để test reaction"""
    from config import ADMIN_ID
    if str(update.effective_user.id) != ADMIN_ID:
        return
    
    text = (
        "🧪 <b>TEST THÔNG BÁO</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        "Đây là tin nhắn test tính năng thả tim!\n"
        f"\n❤️ <b>Thả tim để nhận {REACTION_REWARD:,.0f} Xu!</b>"
    )
    
    try:
        sent_msg = await context.bot.send_message(
            chat_id=MAIN_GROUP_ID, 
            message_thread_id=CHAT_TOPIC_ID, 
            text=text, 
            parse_mode="HTML"
        )
        DAILY_ANNOUNCEMENT_MSG[sent_msg.message_id] = set()
        await update.message.reply_text(f"✅ Đã gửi test! Message ID: {sent_msg.message_id}")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")

bot_app.add_handler(CommandHandler("test_thongbao", test_announcement))

bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
bot_app.add_handler(CallbackQueryHandler(handle_pk_create, pattern="^pk_create_"))
bot_app.add_handler(CallbackQueryHandler(handle_pk_join, pattern="^pk_join$"))
bot_app.add_handler(CallbackQueryHandler(handle_kbb_create, pattern="^kbb_create_"))
bot_app.add_handler(CallbackQueryHandler(handle_kbb_join, pattern="^kbb_join$"))
bot_app.add_handler(CallbackQueryHandler(handle_kbb_choose, pattern="^kbb_choose_"))
bot_app.add_handler(CallbackQueryHandler(handle_game_buttons))

# Handler cho reaction (thả tim nhận Xu)
bot_app.add_handler(MessageReactionHandler(handle_reaction))

@asynccontextmanager
async def lifespan(app: FastAPI):
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    await bot_app.bot.set_my_commands([
        BotCommand("start", "🏠 Về Menu chính"),
        BotCommand("dangky", "📝 Đăng ký nhân viên"),
        BotCommand("me", "💳 Ví & Thẻ"),
        BotCommand("game", "🎰 Chơi Game"),
        BotCommand("diemdanh", "📅 Điểm danh"),
        BotCommand("gift", "🎁 Mở quà may mắn"),
        BotCommand("shop", "🛒 Shop quà"),
        BotCommand("qr", "🚀 Lấy mã QR"),
        BotCommand("top", "🏆 BXH"),
    ])
    asyncio.create_task(bot_app.updater.start_polling())
    asyncio.create_task(run_announcement_scheduler())
    print("✅ Bot đã khởi động với Menu chuẩn...")
    yield
    await bot_app.updater.stop()
    await bot_app.stop()
    await bot_app.shutdown()

app = FastAPI(lifespan=lifespan)

# === CORS MIDDLEWARE - Cho phép POS truy cập API ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cho phép tất cả origins (bao gồm file://)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.head("/ping")
@app.get("/ping")
def ping():
    return {"status": "ok", "message": "Bot is alive!"}

@app.head("/")
@app.get("/", response_class=HTMLResponse)
def home(request: Request, ref: str = None):
    emoji = ""
    if ref:
        db = SessionLocal()
        emp = db.query(Employee).filter(Employee.telegram_id == ref).first()
        if emp:
            emoji = emp.emoji
        db.close()
    return templates.TemplateResponse("index.html", {"request": request, "maps_url": MAPS_URL, "staff_emoji": emoji})

@app.get("/order", response_class=HTMLResponse)
async def webapp_standalone(request: Request):
    return templates.TemplateResponse("webapp_standalone.html", {"request": request})

@app.post("/api/submit_order")
async def api_submit_order(order: OrderData):
    return await submit_order(order, bot_app.bot)

@app.post("/api/verify_pin")
async def verify_pin(request: Request):
    try:
        data = await request.json()
        pin = str(data.get("pin", ""))
        staff = get_staff_by_pin(pin)
        if not staff:
            return {"success": False, "message": "Mã PIN không tồn tại!"}
        return {"success": True, "staff": {"name": staff.get("Tên"), "phone": staff.get("SĐT"), "pin": pin}}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.get("/api/get_review")
def get_review():
    db = SessionLocal()
    review = db.query(Review).order_by(func.random()).first()
    db.close()
    content = review.content if review else random.choice([
        "Trà sữa thơm béo, topping siêu nhiều luôn. 10 điểm!",
        "Quán decor xinh, nước ngon, nhân viên dễ thương.",
        "Trà trái cây tươi mát, uống là nghiền. Sẽ quay lại!",
        "Nước ngon, ship nhanh, nhân viên nhiệt tình. 5 sao!",
        "Trà sữa đậm vị, trân châu dẻo. Sẽ ghé lại!"
    ])
    return {"content": content}


# ==========================================
# API CHO KHI-POS (ĐỒNG BỘ MENU)
# ==========================================

# pending_pos_orders được import từ handlers.order_handlers

@app.get("/api/menu")
def get_menu():
    """API để KHI-POS lấy menu từ KHIBOT"""
    # Menu data - giống với webapp_standalone.html
    categories = [
        {"id": "trasua", "name": "Trà Sữa", "icon": "🧋"},
        {"id": "traicay", "name": "Trà Trái Cây", "icon": "🍹"},
        {"id": "macchiato", "name": "Macchiato", "icon": "🥛"},
        {"id": "dacbiet", "name": "Đặc Biệt", "icon": "⭐"},
        {"id": "topping", "name": "Topping Thêm", "icon": "🍡"},
        {"id": "kotop", "name": "KO TOP", "icon": "🚫"}
    ]
    
    products = [
        # Trà Sữa
        {"id": 1, "cat": "trasua", "name": "Trà Sữa Truyền Thống", "price": 25000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678320/ts-truyenthong_umocuv.jpg"},
        {"id": 2, "cat": "trasua", "name": "Trà Sữa Matcha", "price": 25000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678307/ts-matcha_gobwvh.jpg"},
        {"id": 3, "cat": "trasua", "name": "Trà Sữa Caramel", "price": 25000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678299/ts-caramel_u6vaqg.jpg"},
        {"id": 4, "cat": "trasua", "name": "Trà Sữa Ô Long", "price": 25000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678320/ts-olong_kn2h1c.jpg"},
        {"id": 5, "cat": "trasua", "name": "Trà Sữa Chocolate", "price": 25000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678306/ts-chocolate_kuosxw.jpg"},
        {"id": 6, "cat": "trasua", "name": "Trà Sữa Đào", "price": 25000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678306/ts-dao_jovzy8.jpg"},
        # Trà Trái Cây
        {"id": 10, "cat": "traicay", "name": "Trà Đác Dâu Tằm", "price": 27000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678281/tc-dautam_lifxht.jpg"},
        {"id": 11, "cat": "traicay", "name": "Trà Đác Thơm", "price": 27000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678280/tc-dacthom_s91uyt.jpg"},
        {"id": 12, "cat": "traicay", "name": "Trà Ổi Hồng", "price": 27000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678290/tc-oihong_utnw5w.jpg"},
        {"id": 13, "cat": "traicay", "name": "Trà Nhiệt Đới", "price": 27000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678289/tc-nhietdoi_qzmyyi.jpg"},
        {"id": 14, "cat": "traicay", "name": "Trà Táo Xanh", "price": 27000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678291/tc-taoxanh_ljrgr1.jpg"},
        {"id": 15, "cat": "traicay", "name": "Trà Dưa Lưới", "price": 27000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678281/tc-dualuoi_frskc0.jpg"},
        {"id": 16, "cat": "traicay", "name": "Trà Mãng Cầu", "price": 27000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678282/tc-mangcau_bff6ir.jpg"},
        {"id": 17, "cat": "traicay", "name": "Trà Cóc Hạt Đác", "price": 27000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678276/tc-cochatdac_lat80f.jpg"},
        # Macchiato
        {"id": 20, "cat": "macchiato", "name": "Trà Đào Macchiato", "price": 25000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678264/mc-dao_arsc8z.jpg"},
        {"id": 21, "cat": "macchiato", "name": "Trà Dâu Macchiato", "price": 25000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678266/mc-dau_ythwfg.jpg"},
        {"id": 22, "cat": "macchiato", "name": "Trà Vải Macchiato", "price": 25000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678273/mc-vai_y05t2z.jpg"},
        {"id": 23, "cat": "macchiato", "name": "Hồng Trà Macchiato", "price": 25000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678268/mc-hongtra_dwjbd2.jpg"},
        {"id": 24, "cat": "macchiato", "name": "Ô Long Macchiato", "price": 25000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678270/mc-olong_sqykw6.jpg"},
        {"id": 25, "cat": "macchiato", "name": "Trà Sen Macchiato", "price": 25000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678271/mc-sen_kco8x7.jpg"},
        # Đặc Biệt
        {"id": 30, "cat": "dacbiet", "name": "Trà Sủi", "price": 25000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769679055/Tr%C3%A0_%C4%90%C3%A1c_D%C3%A2u_T%E1%BA%B1m_vxk6nj.jpg"},
        {"id": 31, "cat": "dacbiet", "name": "Sữa Tươi Trân Châu Đ.Đ", "price": 27000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678262/db-suatuoi_ymftil.jpg"},
        {"id": 32, "cat": "dacbiet", "name": "Hồng Trà Latte", "price": 27000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678258/db-hongtralatte_cko07b.jpg"},
        {"id": 33, "cat": "dacbiet", "name": "Matcha Latte", "price": 27000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678261/db-matchalatte_em8slk.jpg"},
        # Topping
        {"id": 100, "cat": "topping", "name": "Thêm Trân Châu", "price": 5000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678298/tp-tranchau_ff3k5o.jpg"},
        {"id": 101, "cat": "topping", "name": "Thêm Củ Năng", "price": 5000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678248/8_tikfnv.jpg"},
        {"id": 102, "cat": "topping", "name": "Thêm Phô Mai", "price": 5000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678247/7_pavlgu.jpg"},
        {"id": 103, "cat": "topping", "name": "Thêm Rau Câu", "price": 5000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769677875/3_davt5n.jpg"},
        {"id": 104, "cat": "topping", "name": "Thêm Khúc Bạch", "price": 5000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769677876/4_fx9ojc.jpg"},
        {"id": 105, "cat": "topping", "name": "Thêm Sương Sáo", "price": 5000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769677875/1_uuksk1.jpg"},
        {"id": 106, "cat": "topping", "name": "Thêm Thạch Đào", "price": 5000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678030/6_ux0ytb.jpg"},
        {"id": 107, "cat": "topping", "name": "Thêm Flan Trứng", "price": 5000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769677875/2_lqjdoz.jpg"},
        {"id": 108, "cat": "topping", "name": "Thêm Ngọc Trai", "price": 5000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769677889/5_wy4gyz.jpg"},
        {"id": 109, "cat": "topping", "name": "Thêm Khoai Dẻo", "price": 5000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678249/9_klh8kn.jpg"},
        {"id": 110, "cat": "topping", "name": "Thêm Đác Thơm", "price": 10000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678252/13_fsntwx.jpg"},
        {"id": 111, "cat": "topping", "name": "Thêm Đác Dâu Tằm", "price": 10000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678250/12_yjvbsp.jpg"},
        {"id": 112, "cat": "topping", "name": "Thêm Trái Cây Nhiệt Đới", "price": 10000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678251/10_oqpadz.jpg"},
        {"id": 113, "cat": "topping", "name": "Thêm Táo Xanh", "price": 10000, "img": "/static/logo.png"},
        {"id": 114, "cat": "topping", "name": "Thêm Dưa Lưới", "price": 10000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678257/16_zirfjx.jpg"},
        {"id": 115, "cat": "topping", "name": "Thêm Ổi Hồng", "price": 10000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678256/15_mwtccy.jpg"},
        {"id": 116, "cat": "topping", "name": "Thêm Mãng Cầu", "price": 10000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678255/14_btqjzs.jpg"},
        {"id": 117, "cat": "topping", "name": "Thêm Macchiato", "price": 5000, "img": "/static/logo.png"},
        {"id": 118, "cat": "topping", "name": "Thêm Full Topping", "price": 10000, "img": "/static/logo.png"},
        {"id": 119, "cat": "topping", "name": "Thêm Đác", "price": 10000, "img": "/static/logo.png"},
        # KO TOPPING - Trà Sữa
        {"id": 200, "cat": "kotop", "subcat": "trasua", "name": "TS Truyền Thống Ko Topping", "price": 19000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678320/ts-truyenthong_umocuv.jpg"},
        {"id": 201, "cat": "kotop", "subcat": "trasua", "name": "TS Matcha Ko Topping", "price": 19000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678307/ts-matcha_gobwvh.jpg"},
        {"id": 202, "cat": "kotop", "subcat": "trasua", "name": "TS Caramel Ko Topping", "price": 19000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678299/ts-caramel_u6vaqg.jpg"},
        {"id": 203, "cat": "kotop", "subcat": "trasua", "name": "TS Ô Long Ko Topping", "price": 19000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678320/ts-olong_kn2h1c.jpg"},
        {"id": 204, "cat": "kotop", "subcat": "trasua", "name": "TS Chocolate Ko Topping", "price": 19000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678306/ts-chocolate_kuosxw.jpg"},
        {"id": 205, "cat": "kotop", "subcat": "trasua", "name": "TS Đào Ko Topping", "price": 19000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678306/ts-dao_jovzy8.jpg"},
        # KO TOPPING - Macchiato
        {"id": 210, "cat": "kotop", "subcat": "macchiato", "name": "Trà Đào Ko Topping", "price": 19000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678264/mc-dao_arsc8z.jpg"},
        {"id": 211, "cat": "kotop", "subcat": "macchiato", "name": "Trà Dâu Ko Topping", "price": 19000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678266/mc-dau_ythwfg.jpg"},
        {"id": 212, "cat": "kotop", "subcat": "macchiato", "name": "Trà Vải Ko Topping", "price": 19000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678273/mc-vai_y05t2z.jpg"},
        {"id": 213, "cat": "kotop", "subcat": "macchiato", "name": "Hồng Trà Ko Topping", "price": 19000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678268/mc-hongtra_dwjbd2.jpg"},
        {"id": 214, "cat": "kotop", "subcat": "macchiato", "name": "Ô Long Ko Topping", "price": 19000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678270/mc-olong_sqykw6.jpg"},
        {"id": 215, "cat": "kotop", "subcat": "macchiato", "name": "Trà Sen Ko Topping", "price": 19000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678271/mc-sen_kco8x7.jpg"},
        # KO TOPPING - Đặc Biệt
        {"id": 220, "cat": "kotop", "subcat": "dacbiet", "name": "Trà Sủi Ko Topping", "price": 19000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769679055/Tr%C3%A0_%C4%90%C3%A1c_D%C3%A2u_T%E1%BA%B1m_vxk6nj.jpg"},
        {"id": 221, "cat": "kotop", "subcat": "dacbiet", "name": "Hồng Trà Latte Ko Topping", "price": 22000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678258/db-hongtralatte_cko07b.jpg"},
        {"id": 222, "cat": "kotop", "subcat": "dacbiet", "name": "Matcha Latte Ko Topping", "price": 22000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678261/db-matchalatte_em8slk.jpg"},
        # KO TOPPING - Trái Cây
        {"id": 230, "cat": "kotop", "subcat": "traicay", "name": "Trà Đác Dâu Tằm Ko Topping", "price": 19000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678281/tc-dautam_lifxht.jpg"},
        {"id": 231, "cat": "kotop", "subcat": "traicay", "name": "Trà Đác Thơm Ko Topping", "price": 19000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678280/tc-dacthom_s91uyt.jpg"},
        {"id": 232, "cat": "kotop", "subcat": "traicay", "name": "Trà Ổi Hồng Ko Topping", "price": 19000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678290/tc-oihong_utnw5w.jpg"},
        {"id": 233, "cat": "kotop", "subcat": "traicay", "name": "Trà Nhiệt Đới Ko Topping", "price": 19000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678289/tc-nhietdoi_qzmyyi.jpg"},
        {"id": 234, "cat": "kotop", "subcat": "traicay", "name": "Trà Táo Xanh Ko Topping", "price": 19000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678291/tc-taoxanh_ljrgr1.jpg"},
        {"id": 235, "cat": "kotop", "subcat": "traicay", "name": "Trà Dưa Lưới Ko Topping", "price": 19000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678281/tc-dualuoi_frskc0.jpg"},
        {"id": 236, "cat": "kotop", "subcat": "traicay", "name": "Trà Mãng Cầu Ko Topping", "price": 19000, "img": "/static/logo.png"},
        {"id": 237, "cat": "kotop", "subcat": "traicay", "name": "Trà Cóc Hạt Đác Ko Topping", "price": 19000, "img": "https://res.cloudinary.com/anhduy/image/upload/v1769678276/tc-cochatdac_lat80f.jpg"}
    ]
    
    toppings = [
        {"name": "Trân Châu", "price": 5000},
        {"name": "Củ Năng", "price": 5000},
        {"name": "Phô Mai", "price": 5000},
        {"name": "Rau Câu", "price": 5000},
        {"name": "Khúc Bạch", "price": 5000},
        {"name": "Sương Sáo", "price": 5000},
        {"name": "Thạch Đào", "price": 5000},
        {"name": "Flan Trứng", "price": 5000},
        {"name": "Ngọc Trai", "price": 5000},
        {"name": "Khoai Dẻo", "price": 5000},
        {"name": "Đác Thơm", "price": 10000},
        {"name": "Đác Dâu Tằm", "price": 10000},
        {"name": "Trái Cây Nhiệt Đới", "price": 10000},
        {"name": "Táo Xanh", "price": 10000},
        {"name": "Dưa Lưới", "price": 10000},
        {"name": "Ổi Hồng", "price": 10000},
        {"name": "Mãng Cầu", "price": 10000}
    ]
    
    return {
        "success": True,
        "menu": {
            "categories": categories,
            "products": products,
            "toppings": toppings
        }
    }


@app.get("/api/pending_orders")
def api_pending_orders():
    """API để KHI-POS lấy danh sách order chờ xử lý"""
    orders = get_pending_orders_list()
    return {"orders": orders, "count": len(orders)}


@app.post("/api/order_accepted")
async def api_order_accepted(request: Request):
    """API khi KHI-POS đã nhận order"""
    try:
        data = await request.json()
        order_id = data.get("order_id")
        remove_pending_order(order_id)
        return {"success": True, "message": f"Order {order_id} đã được xử lý"}
    except Exception as e:
        return {"success": False, "message": str(e)}
@app.get("/api/menu_v2")
def get_menu_v2():
    """API mới - Lấy menu từ database"""
    db = SessionLocal()
    try:
        # Lấy categories
        categories = db.query(MenuCategory).filter(
            MenuCategory.is_active == True
        ).order_by(MenuCategory.sort_order).all()
        
        # Lấy products
        products = db.query(MenuProduct).filter(
            MenuProduct.is_active == True
        ).order_by(MenuProduct.sort_order).all()
        
        # Lấy toppings
        toppings = db.query(MenuTopping).filter(
            MenuTopping.is_active == True
        ).order_by(MenuTopping.sort_order).all()
        
        # Lấy quick notes
        quick_notes = db.query(MenuQuickNote).filter(
            MenuQuickNote.is_active == True
        ).order_by(MenuQuickNote.sort_order).all()
        
        return {
            "success": True,
            "menu": {
                "categories": [
                    {"id": c.id, "name": c.name, "icon": c.icon}
                    for c in categories
                ],
                "products": [
                    {
                        "id": p.id, 
                        "cat": p.category_id, 
                        "name": p.name, 
                        "price": p.price, 
                        "img": p.image
                    }
                    for p in products
                ],
                "toppings": [
                    {"id": t.id, "name": t.name, "price": t.price, "type": t.topping_type}
                    for t in toppings
                ],
                "quick_notes": [
                    {"id": n.id, "text": n.text}
                    for n in quick_notes
                ]
            }
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


# ============================
# API SEED - IMPORT DATA TỪ HARDCODE VÀO DB
# ============================

@app.api_route("/api/admin/add-new-toppings", methods=["GET", "POST"])
def add_new_toppings():
    """Thêm 3 topping mới vào database (không reset)"""
    db = SessionLocal()
    try:
        new_toppings = [
            {"category_id": "topping", "name": "Thêm Macchiato", "price": 5000, "image": "/static/logo.png", "sort_order": 18},
            {"category_id": "topping", "name": "Thêm Full Topping", "price": 10000, "image": "/static/logo.png", "sort_order": 19},
            {"category_id": "topping", "name": "Thêm Đác", "price": 10000, "image": "/static/logo.png", "sort_order": 20},
        ]
        
        added = 0
        for t in new_toppings:
            # Kiểm tra đã có chưa
            exists = db.query(MenuProduct).filter(MenuProduct.name == t["name"]).first()
            if not exists:
                db.add(MenuProduct(**t))
                added += 1
        
        db.commit()
        return {"success": True, "message": f"Đã thêm {added} topping mới", "added": added}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

@app.post("/api/admin/seed")
def seed_menu_data():
    """Import data từ hardcode vào database (chạy 1 lần)"""
    db = SessionLocal()
    try:
        # Kiểm tra đã có data chưa
        if db.query(MenuCategory).count() > 0:
            return {"success": False, "message": "Database đã có data, không cần seed lại"}
        
        # === SEED CATEGORIES ===
        categories_data = [
            {"id": "trasua", "name": "Trà Sữa", "icon": "🧋", "sort_order": 1},
            {"id": "traicay", "name": "Trà Trái Cây", "icon": "🍹", "sort_order": 2},
            {"id": "macchiato", "name": "Macchiato", "icon": "🥛", "sort_order": 3},
            {"id": "dacbiet", "name": "Đặc Biệt", "icon": "⭐", "sort_order": 4},
            {"id": "topping", "name": "Topping Thêm", "icon": "🍡", "sort_order": 5},
            {"id": "kotop", "name": "KO TOP", "icon": "🚫", "sort_order": 6},
        ]
        for c in categories_data:
            db.add(MenuCategory(**c))
        
        # === SEED PRODUCTS ===
        products_data = [
            # Trà Sữa
            {"category_id": "trasua", "name": "Trà Sữa Truyền Thống", "price": 25000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678320/ts-truyenthong_umocuv.jpg", "sort_order": 1},
            {"category_id": "trasua", "name": "Trà Sữa Matcha", "price": 25000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678307/ts-matcha_gobwvh.jpg", "sort_order": 2},
            {"category_id": "trasua", "name": "Trà Sữa Caramel", "price": 25000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678299/ts-caramel_u6vaqg.jpg", "sort_order": 3},
            {"category_id": "trasua", "name": "Trà Sữa Ô Long", "price": 25000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678320/ts-olong_kn2h1c.jpg", "sort_order": 4},
            {"category_id": "trasua", "name": "Trà Sữa Chocolate", "price": 25000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678306/ts-chocolate_kuosxw.jpg", "sort_order": 5},
            {"category_id": "trasua", "name": "Trà Sữa Đào", "price": 25000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678306/ts-dao_jovzy8.jpg", "sort_order": 6},
            # Trà Trái Cây
            {"category_id": "traicay", "name": "Trà Đác Dâu Tằm", "price": 27000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678281/tc-dautam_lifxht.jpg", "sort_order": 1},
            {"category_id": "traicay", "name": "Trà Đác Thơm", "price": 27000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678280/tc-dacthom_s91uyt.jpg", "sort_order": 2},
            {"category_id": "traicay", "name": "Trà Ổi Hồng", "price": 27000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678290/tc-oihong_utnw5w.jpg", "sort_order": 3},
            {"category_id": "traicay", "name": "Trà Nhiệt Đới", "price": 27000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678289/tc-nhietdoi_qzmyyi.jpg", "sort_order": 4},
            {"category_id": "traicay", "name": "Trà Táo Xanh", "price": 27000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678291/tc-taoxanh_ljrgr1.jpg", "sort_order": 5},
            {"category_id": "traicay", "name": "Trà Dưa Lưới", "price": 27000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678281/tc-dualuoi_frskc0.jpg", "sort_order": 6},
            {"category_id": "traicay", "name": "Trà Mãng Cầu", "price": 27000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678282/tc-mangcau_bff6ir.jpg", "sort_order": 7},
            {"category_id": "traicay", "name": "Trà Cóc Hạt Đác", "price": 27000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678276/tc-cochatdac_lat80f.jpg", "sort_order": 8},
            # Macchiato
            {"category_id": "macchiato", "name": "Trà Đào Macchiato", "price": 25000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678264/mc-dao_arsc8z.jpg", "sort_order": 1},
            {"category_id": "macchiato", "name": "Trà Dâu Macchiato", "price": 25000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678266/mc-dau_ythwfg.jpg", "sort_order": 2},
            {"category_id": "macchiato", "name": "Trà Vải Macchiato", "price": 25000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678273/mc-vai_y05t2z.jpg", "sort_order": 3},
            {"category_id": "macchiato", "name": "Hồng Trà Macchiato", "price": 25000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678268/mc-hongtra_dwjbd2.jpg", "sort_order": 4},
            {"category_id": "macchiato", "name": "Ô Long Macchiato", "price": 25000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678270/mc-olong_sqykw6.jpg", "sort_order": 5},
            {"category_id": "macchiato", "name": "Trà Sen Macchiato", "price": 25000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678271/mc-sen_kco8x7.jpg", "sort_order": 6},
            # Đặc Biệt
            {"category_id": "dacbiet", "name": "Trà Sủi", "price": 25000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769679055/Tr%C3%A0_%C4%90%C3%A1c_D%C3%A2u_T%E1%BA%B1m_vxk6nj.jpg", "sort_order": 1},
            {"category_id": "dacbiet", "name": "Sữa Tươi Trân Châu Đ.Đ", "price": 27000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678262/db-suatuoi_ymftil.jpg", "sort_order": 2},
            {"category_id": "dacbiet", "name": "Hồng Trà Latte", "price": 27000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678258/db-hongtralatte_cko07b.jpg", "sort_order": 3},
            {"category_id": "dacbiet", "name": "Matcha Latte", "price": 27000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678261/db-matchalatte_em8slk.jpg", "sort_order": 4},
            # Topping
            {"category_id": "topping", "name": "Thêm Trân Châu", "price": 5000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678298/tp-tranchau_ff3k5o.jpg", "sort_order": 1},
            {"category_id": "topping", "name": "Thêm Củ Năng", "price": 5000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678248/8_tikfnv.jpg", "sort_order": 2},
            {"category_id": "topping", "name": "Thêm Phô Mai", "price": 5000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678247/7_pavlgu.jpg", "sort_order": 3},
            {"category_id": "topping", "name": "Thêm Rau Câu", "price": 5000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769677875/3_davt5n.jpg", "sort_order": 4},
            {"category_id": "topping", "name": "Thêm Khúc Bạch", "price": 5000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769677876/4_fx9ojc.jpg", "sort_order": 5},
            {"category_id": "topping", "name": "Thêm Sương Sáo", "price": 5000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769677875/1_uuksk1.jpg", "sort_order": 6},
            {"category_id": "topping", "name": "Thêm Thạch Đào", "price": 5000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678030/6_ux0ytb.jpg", "sort_order": 7},
            {"category_id": "topping", "name": "Thêm Flan Trứng", "price": 5000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769677875/2_lqjdoz.jpg", "sort_order": 8},
            {"category_id": "topping", "name": "Thêm Ngọc Trai", "price": 5000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769677889/5_wy4gyz.jpg", "sort_order": 9},
            {"category_id": "topping", "name": "Thêm Khoai Dẻo", "price": 5000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678249/9_klh8kn.jpg", "sort_order": 10},
            {"category_id": "topping", "name": "Thêm Đác Thơm", "price": 10000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678252/13_fsntwx.jpg", "sort_order": 11},
            {"category_id": "topping", "name": "Thêm Đác Dâu Tằm", "price": 10000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678250/12_yjvbsp.jpg", "sort_order": 12},
            {"category_id": "topping", "name": "Thêm Trái Cây Nhiệt Đới", "price": 10000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678251/10_oqpadz.jpg", "sort_order": 13},
            {"category_id": "topping", "name": "Thêm Táo Xanh", "price": 10000, "image": "/static/logo.png", "sort_order": 14},
            {"category_id": "topping", "name": "Thêm Dưa Lưới", "price": 10000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678257/16_zirfjx.jpg", "sort_order": 15},
            {"category_id": "topping", "name": "Thêm Ổi Hồng", "price": 10000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678256/15_mwtccy.jpg", "sort_order": 16},
            {"category_id": "topping", "name": "Thêm Mãng Cầu", "price": 10000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678255/14_btqjzs.jpg", "sort_order": 17},
            {"category_id": "topping", "name": "Thêm Macchiato", "price": 5000, "image": "/static/logo.png", "sort_order": 18},
            {"category_id": "topping", "name": "Thêm Full Topping", "price": 10000, "image": "/static/logo.png", "sort_order": 19},
            {"category_id": "topping", "name": "Thêm Đác", "price": 10000, "image": "/static/logo.png", "sort_order": 20},
            # KO TOPPING - Trà Sữa
            {"category_id": "kotop", "name": "TS Truyền Thống Ko Topping", "price": 19000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678320/ts-truyenthong_umocuv.jpg", "sort_order": 1},
            {"category_id": "kotop", "name": "TS Matcha Ko Topping", "price": 19000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678307/ts-matcha_gobwvh.jpg", "sort_order": 2},
            {"category_id": "kotop", "name": "TS Caramel Ko Topping", "price": 19000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678299/ts-caramel_u6vaqg.jpg", "sort_order": 3},
            {"category_id": "kotop", "name": "TS Ô Long Ko Topping", "price": 19000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678320/ts-olong_kn2h1c.jpg", "sort_order": 4},
            {"category_id": "kotop", "name": "TS Chocolate Ko Topping", "price": 19000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678306/ts-chocolate_kuosxw.jpg", "sort_order": 5},
            {"category_id": "kotop", "name": "TS Đào Ko Topping", "price": 19000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678306/ts-dao_jovzy8.jpg", "sort_order": 6},
            # KO TOPPING - Macchiato
            {"category_id": "kotop", "name": "Trà Đào Ko Topping", "price": 19000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678264/mc-dao_arsc8z.jpg", "sort_order": 7},
            {"category_id": "kotop", "name": "Trà Dâu Ko Topping", "price": 19000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678266/mc-dau_ythwfg.jpg", "sort_order": 8},
            {"category_id": "kotop", "name": "Trà Vải Ko Topping", "price": 19000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678273/mc-vai_y05t2z.jpg", "sort_order": 9},
            {"category_id": "kotop", "name": "Hồng Trà Ko Topping", "price": 19000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678268/mc-hongtra_dwjbd2.jpg", "sort_order": 10},
            {"category_id": "kotop", "name": "Ô Long Ko Topping", "price": 19000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678270/mc-olong_sqykw6.jpg", "sort_order": 11},
            {"category_id": "kotop", "name": "Trà Sen Ko Topping", "price": 19000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678271/mc-sen_kco8x7.jpg", "sort_order": 12},
            # KO TOPPING - Đặc Biệt
            {"category_id": "kotop", "name": "Trà Sủi Ko Topping", "price": 19000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769679055/Tr%C3%A0_%C4%90%C3%A1c_D%C3%A2u_T%E1%BA%B1m_vxk6nj.jpg", "sort_order": 13},
            {"category_id": "kotop", "name": "Hồng Trà Latte Ko Topping", "price": 22000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678258/db-hongtralatte_cko07b.jpg", "sort_order": 14},
            {"category_id": "kotop", "name": "Matcha Latte Ko Topping", "price": 22000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678261/db-matchalatte_em8slk.jpg", "sort_order": 15},
            # KO TOPPING - Trái Cây
            {"category_id": "kotop", "name": "Trà Đác Dâu Tằm Ko Topping", "price": 19000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678281/tc-dautam_lifxht.jpg", "sort_order": 16},
            {"category_id": "kotop", "name": "Trà Đác Thơm Ko Topping", "price": 19000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678280/tc-dacthom_s91uyt.jpg", "sort_order": 17},
            {"category_id": "kotop", "name": "Trà Ổi Hồng Ko Topping", "price": 19000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678290/tc-oihong_utnw5w.jpg", "sort_order": 18},
            {"category_id": "kotop", "name": "Trà Nhiệt Đới Ko Topping", "price": 19000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678289/tc-nhietdoi_qzmyyi.jpg", "sort_order": 19},
            {"category_id": "kotop", "name": "Trà Táo Xanh Ko Topping", "price": 19000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678291/tc-taoxanh_ljrgr1.jpg", "sort_order": 20},
            {"category_id": "kotop", "name": "Trà Dưa Lưới Ko Topping", "price": 19000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678281/tc-dualuoi_frskc0.jpg", "sort_order": 21},
            {"category_id": "kotop", "name": "Trà Mãng Cầu Ko Topping", "price": 19000, "image": "/static/logo.png", "sort_order": 22},
            {"category_id": "kotop", "name": "Trà Cóc Hạt Đác Ko Topping", "price": 19000, "image": "https://res.cloudinary.com/anhduy/image/upload/v1769678276/tc-cochatdac_lat80f.jpg", "sort_order": 23},
        ]
        for p in products_data:
            db.add(MenuProduct(**p))
        
        # === SEED TOPPINGS ===
        toppings_data = [
            {"name": "Trân Châu", "price": 5000, "topping_type": "basic", "sort_order": 1},
            {"name": "Củ Năng", "price": 5000, "topping_type": "basic", "sort_order": 2},
            {"name": "Phô Mai", "price": 5000, "topping_type": "basic", "sort_order": 3},
            {"name": "Rau Câu", "price": 5000, "topping_type": "basic", "sort_order": 4},
            {"name": "Khúc Bạch", "price": 5000, "topping_type": "basic", "sort_order": 5},
            {"name": "Sương Sáo", "price": 5000, "topping_type": "basic", "sort_order": 6},
            {"name": "Thạch Đào", "price": 5000, "topping_type": "basic", "sort_order": 7},
            {"name": "Flan Trứng", "price": 5000, "topping_type": "basic", "sort_order": 8},
            {"name": "Ngọc Trai", "price": 5000, "topping_type": "basic", "sort_order": 9},
            {"name": "Khoai Dẻo", "price": 5000, "topping_type": "basic", "sort_order": 10},
            {"name": "Đác Thơm", "price": 10000, "topping_type": "fruit", "sort_order": 11},
            {"name": "Đác Dâu Tằm", "price": 10000, "topping_type": "fruit", "sort_order": 12},
            {"name": "Trái Cây Nhiệt Đới", "price": 10000, "topping_type": "fruit", "sort_order": 13},
            {"name": "Táo Xanh", "price": 10000, "topping_type": "fruit", "sort_order": 14},
            {"name": "Dưa Lưới", "price": 10000, "topping_type": "fruit", "sort_order": 15},
            {"name": "Ổi Hồng", "price": 10000, "topping_type": "fruit", "sort_order": 16},
            {"name": "Mãng Cầu", "price": 10000, "topping_type": "fruit", "sort_order": 17},
        ]
        for t in toppings_data:
            db.add(MenuTopping(**t))
        
        # === SEED QUICK NOTES ===
        notes_data = [
            {"text": "Ít đá", "sort_order": 1},
            {"text": "Không đá", "sort_order": 2},
            {"text": "Ít ngọt", "sort_order": 3},
            {"text": "Nhiều ngọt", "sort_order": 4},
            {"text": "Mang về", "sort_order": 5},
            {"text": "Làm chua", "sort_order": 6},
            {"text": "Ít chua", "sort_order": 7},
            {"text": "Đậy nắp", "sort_order": 8},
            {"text": "Ép nắp", "sort_order": 9},
            {"text": "Ko kem", "sort_order": 10},
            {"text": "Kem riêng", "sort_order": 11},
            {"text": "Đá riêng", "sort_order": 12},
        ]
        for n in notes_data:
            db.add(MenuQuickNote(**n))
        
        db.commit()
        return {
            "success": True, 
            "message": "Đã import data vào database",
            "stats": {
                "categories": len(categories_data),
                "products": len(products_data),
                "toppings": len(toppings_data),
                "quick_notes": len(notes_data)
            }
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


# ============================
# API CRUD - QUẢN LÝ MENU
# ============================

# --- CATEGORIES ---
@app.post("/api/admin/category")
async def add_category(request: Request):
    """Thêm danh mục mới"""
    db = SessionLocal()
    try:
        data = await request.json()
        category = MenuCategory(
            id=data.get("id"),
            name=data.get("name"),
            icon=data.get("icon", "📁"),
            sort_order=data.get("sort_order", 0),
            is_active=True
        )
        db.add(category)
        db.commit()
        return {"success": True, "message": "Đã thêm danh mục"}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

@app.put("/api/admin/category/{cat_id}")
async def update_category(cat_id: str, request: Request):
    """Sửa danh mục"""
    db = SessionLocal()
    try:
        data = await request.json()
        category = db.query(MenuCategory).filter(MenuCategory.id == cat_id).first()
        if not category:
            return {"success": False, "error": "Không tìm thấy danh mục"}
        
        if "name" in data: category.name = data["name"]
        if "icon" in data: category.icon = data["icon"]
        if "sort_order" in data: category.sort_order = data["sort_order"]
        if "is_active" in data: category.is_active = data["is_active"]
        
        db.commit()
        return {"success": True, "message": "Đã cập nhật danh mục"}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

@app.delete("/api/admin/category/{cat_id}")
def delete_category(cat_id: str):
    """Xóa danh mục (soft delete)"""
    db = SessionLocal()
    try:
        category = db.query(MenuCategory).filter(MenuCategory.id == cat_id).first()
        if not category:
            return {"success": False, "error": "Không tìm thấy danh mục"}
        category.is_active = False
        db.commit()
        return {"success": True, "message": "Đã xóa danh mục"}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

# --- PRODUCTS ---
@app.post("/api/admin/product")
async def add_product(request: Request):
    """Thêm sản phẩm mới"""
    db = SessionLocal()
    try:
        data = await request.json()
        product = MenuProduct(
            category_id=data.get("category_id"),
            name=data.get("name"),
            price=data.get("price", 0),
            image=data.get("image", ""),
            sort_order=data.get("sort_order", 0),
            is_active=True
        )
        db.add(product)
        db.commit()
        db.refresh(product)
        return {"success": True, "message": "Đã thêm sản phẩm", "id": product.id}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

@app.put("/api/admin/product/{product_id}")
async def update_product(product_id: int, request: Request):
    """Sửa sản phẩm"""
    db = SessionLocal()
    try:
        data = await request.json()
        product = db.query(MenuProduct).filter(MenuProduct.id == product_id).first()
        if not product:
            return {"success": False, "error": "Không tìm thấy sản phẩm"}
        
        if "name" in data: product.name = data["name"]
        if "price" in data: product.price = data["price"]
        if "image" in data: product.image = data["image"]
        if "category_id" in data: product.category_id = data["category_id"]
        if "sort_order" in data: product.sort_order = data["sort_order"]
        if "is_active" in data: product.is_active = data["is_active"]
        
        db.commit()
        return {"success": True, "message": "Đã cập nhật sản phẩm"}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

@app.delete("/api/admin/product/{product_id}")
def delete_product(product_id: int):
    """Xóa sản phẩm (soft delete)"""
    db = SessionLocal()
    try:
        product = db.query(MenuProduct).filter(MenuProduct.id == product_id).first()
        if not product:
            return {"success": False, "error": "Không tìm thấy sản phẩm"}
        product.is_active = False
        db.commit()
        return {"success": True, "message": "Đã xóa sản phẩm"}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

# --- TOPPINGS ---
@app.post("/api/admin/topping")
async def add_topping(request: Request):
    """Thêm topping mới"""
    db = SessionLocal()
    try:
        data = await request.json()
        topping = MenuTopping(
            name=data.get("name"),
            price=data.get("price", 5000),
            topping_type=data.get("topping_type", "basic"),
            sort_order=data.get("sort_order", 0),
            is_active=True
        )
        db.add(topping)
        db.commit()
        db.refresh(topping)
        return {"success": True, "message": "Đã thêm topping", "id": topping.id}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

@app.put("/api/admin/topping/{topping_id}")
async def update_topping(topping_id: int, request: Request):
    """Sửa topping"""
    db = SessionLocal()
    try:
        data = await request.json()
        topping = db.query(MenuTopping).filter(MenuTopping.id == topping_id).first()
        if not topping:
            return {"success": False, "error": "Không tìm thấy topping"}
        
        if "name" in data: topping.name = data["name"]
        if "price" in data: topping.price = data["price"]
        if "topping_type" in data: topping.topping_type = data["topping_type"]
        if "sort_order" in data: topping.sort_order = data["sort_order"]
        if "is_active" in data: topping.is_active = data["is_active"]
        
        db.commit()
        return {"success": True, "message": "Đã cập nhật topping"}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

@app.delete("/api/admin/topping/{topping_id}")
def delete_topping(topping_id: int):
    """Xóa topping (soft delete)"""
    db = SessionLocal()
    try:
        topping = db.query(MenuTopping).filter(MenuTopping.id == topping_id).first()
        if not topping:
            return {"success": False, "error": "Không tìm thấy topping"}
        topping.is_active = False
        db.commit()
        return {"success": True, "message": "Đã xóa topping"}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

# --- QUICK NOTES ---
@app.post("/api/admin/note")
async def add_note(request: Request):
    """Thêm ghi chú nhanh"""
    db = SessionLocal()
    try:
        data = await request.json()
        note = MenuQuickNote(
            text=data.get("text"),
            sort_order=data.get("sort_order", 0),
            is_active=True
        )
        db.add(note)
        db.commit()
        db.refresh(note)
        return {"success": True, "message": "Đã thêm ghi chú", "id": note.id}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

@app.put("/api/admin/note/{note_id}")
async def update_note(note_id: int, request: Request):
    """Sửa ghi chú"""
    db = SessionLocal()
    try:
        data = await request.json()
        note = db.query(MenuQuickNote).filter(MenuQuickNote.id == note_id).first()
        if not note:
            return {"success": False, "error": "Không tìm thấy ghi chú"}
        
        if "text" in data: note.text = data["text"]
        if "sort_order" in data: note.sort_order = data["sort_order"]
        if "is_active" in data: note.is_active = data["is_active"]
        
        db.commit()
        return {"success": True, "message": "Đã cập nhật ghi chú"}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

@app.delete("/api/admin/note/{note_id}")
def delete_note(note_id: int):
    """Xóa ghi chú (soft delete)"""
    db = SessionLocal()
    try:
        note = db.query(MenuQuickNote).filter(MenuQuickNote.id == note_id).first()
        if not note:
            return {"success": False, "error": "Không tìm thấy ghi chú"}
        note.is_active = False
        db.commit()
        return {"success": True, "message": "Đã xóa ghi chú"}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

