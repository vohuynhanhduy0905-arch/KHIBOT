# --- FILE: main.py ---
# Bot Mì Cay ITADA - Phiên bản tối ưu với modules
# ĐÃ CẬP NHẬT: Giới hạn game Tài Xỉu

import asyncio
import random
from datetime import datetime, timedelta, date
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

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
from database import init_db, SessionLocal, Employee, Review, ShopLog
from staff_sheet import get_staff_by_pin, get_all_staff

from handlers import (
    start_command, me_command, qr_command, top_command,
    daily_command, gift_command, shop_command,
    get_main_menu, check_private,
    dangky_command, dsnv_command, xoanv_command, broadcast_command,
    game_ui_command, slot_command, kbb_command,
    handle_slot_menu, handle_slot_play,
    handle_kbb_create, handle_kbb_join, handle_kbb_choose,
    handle_pk_create, handle_pk_join,
    order_command, submit_order, order_button_callback, OrderData
)

init_db()
# === ĐỒNG BỘ EMOJI TỪ DATABASE → GOOGLE SHEET KHI KHỞI ĐỘNG ===
def sync_emoji_to_sheet():
    """Đồng bộ emoji từ Database lên Google Sheet 1 lần khi khởi động"""
    try:
        print("🔄 Đang đồng bộ emoji từ Database → Google Sheet...")
        
        import gspread
        import os
        import json
        from oauth2client.service_account import ServiceAccountCredentials
        
        # Kết nối Google Sheet
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        service_account_info = os.environ.get("GOOGLE_SERVICE_ACCOUNT")
        
        if not service_account_info:
            print("⚠️ Không tìm thấy GOOGLE_SERVICE_ACCOUNT, bỏ qua sync emoji")
            return
        
        creds_dict = json.loads(service_account_info)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        
        client = gspread.authorize(creds)
        spreadsheet = client.open("ITADA REVIEW MAP")
        sheet = spreadsheet.worksheet("NHANVIEN")
        
        # Lấy data từ Sheet
        records = sheet.get_all_records()
        tg_to_row = {}
        for i, r in enumerate(records):
            tg_id = str(r.get("Telegram_ID", "")).strip()
            if tg_id:
                tg_to_row[tg_id] = i + 2  # +2 vì row 1 là header
        
        # Lấy data từ Database
        db = SessionLocal()
        employees = db.query(Employee).all()
        
        updated = 0
        for emp in employees:
            tg_id = str(emp.telegram_id).strip()
            db_emoji = str(emp.emoji).strip() if emp.emoji else ""
            
            if tg_id in tg_to_row and db_emoji:
                row_num = tg_to_row[tg_id]
                sheet_emoji = str(records[row_num - 2].get("Emoji", "")).strip()
                
                if db_emoji != sheet_emoji:
                    sheet.update_cell(row_num, 5, db_emoji)  # Cột 5 = Emoji
                    print(f"  ✅ {emp.name}: {sheet_emoji} → {db_emoji}")
                    updated += 1
        
        db.close()
        print(f"✅ Đồng bộ emoji hoàn tất! Cập nhật {updated} nhân viên.")
    except Exception as e:
        print(f"⚠️ Lỗi đồng bộ emoji (bỏ qua): {e}")

# Chạy đồng bộ khi khởi động - trong try-catch để không block app
try:
    sync_emoji_to_sheet()
except Exception as e:
    print(f"⚠️ Sync emoji failed, continuing... {e}")
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
    # === THÊM LOG DEBUG ===
    print(f"🔔 REACTION RECEIVED!")
    print(f"   Update: {update}")
    # === KẾT THÚC LOG ===
    
    try:
        reaction = update.message_reaction
        
        # === THÊM LOG DEBUG ===
        print(f"   reaction: {reaction}")
        print(f"   MAIN_GROUP_ID: {MAIN_GROUP_ID}")
        print(f"   DAILY_ANNOUNCEMENT_MSG: {DAILY_ANNOUNCEMENT_MSG}")
        # === KẾT THÚC LOG ===
        
        if not reaction:
            print("   ❌ reaction is None")
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
            [InlineKeyboardButton("🎲 Tài Xỉu", callback_data="menu_tx"), InlineKeyboardButton("🎰 Slot", callback_data="slot_menu")],
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
    
    if data == "slot_menu":
        await handle_slot_menu(update, context)
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
bot_app.add_handler(CommandHandler("slot", slot_command))
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
bot_app.add_handler(CallbackQueryHandler(order_button_callback, pattern="^(cancel_order_|pos_done)"))
bot_app.add_handler(CallbackQueryHandler(handle_slot_play, pattern="^slot_play_"))
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
    asyncio.create_task(bot_app.updater.start_polling(
    allowed_updates=[
        "message", 
        "edited_message",
        "callback_query", 
        "message_reaction",
        "my_chat_member",
        "chat_member"
    ]
))
    asyncio.create_task(run_announcement_scheduler())
    print("✅ Bot Mì Cay ITADA đã khởi động...")
    yield
    await bot_app.updater.stop()
    await bot_app.stop()
    await bot_app.shutdown()

app = FastAPI(lifespan=lifespan)
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
        "Mì cay nước dùng đậm đà, rất vừa miệng. Nhân viên luôn mỉm cười!",
        "Nhân viên phục vụ nhanh nhẹn, mì cay hải sản tuyệt vời!",
        "Không gian thoáng mát, sạch sẽ. Mì Cay ITADA quá đỉnh!",
        "Đồ ăn ra nhanh, nóng hổi. Sẽ quay lại ủng hộ!",
        "Giá cả hợp lý, chất lượng tuyệt vời. 5 sao!"
    ])
    return {"content": content}


@app.get("/api/sync_emoji_from_sheet")
def sync_emoji_from_sheet_api():
    """API để sync emoji từ Google Sheet vào Database (chạy 1 lần)"""
    try:
        import gspread
        import os
        import json
        from oauth2client.service_account import ServiceAccountCredentials
        
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        service_account_info = os.environ.get("GOOGLE_SERVICE_ACCOUNT")
        
        if not service_account_info:
            return {"success": False, "message": "Không tìm thấy GOOGLE_SERVICE_ACCOUNT"}
        
        creds_dict = json.loads(service_account_info)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        
        client = gspread.authorize(creds)
        spreadsheet = client.open("ITADA REVIEW MAP")
        sheet = spreadsheet.worksheet("NHANVIEN")
        
        records = sheet.get_all_records()
        
        db = SessionLocal()
        updated = 0
        created = 0
        results = []
        
        for staff in records:
            tg_id = str(staff.get("Telegram_ID", "")).strip()
            sheet_emoji = str(staff.get("Emoji", "")).strip()
            name = str(staff.get("Tên", "")).strip()
            
            if not tg_id:
                continue
            
            emp = db.query(Employee).filter(Employee.telegram_id == tg_id).first()
            
            if emp:
                if sheet_emoji and emp.emoji != sheet_emoji:
                    old_emoji = emp.emoji
                    emp.emoji = sheet_emoji
                    updated += 1
                    results.append(f"✅ {name}: {old_emoji} → {sheet_emoji}")
            else:
                # Tạo mới employee nếu chưa có trong DB
                if sheet_emoji:
                    new_emp = Employee(telegram_id=tg_id, name=name, emoji=sheet_emoji)
                    db.add(new_emp)
                    created += 1
                    results.append(f"🆕 {name}: {sheet_emoji}")
        
        db.commit()
        db.close()
        
        return {
            "success": True, 
            "updated": updated,
            "created": created,
            "details": results
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.get("/api/debug_emoji")
def debug_emoji():
    """API debug để xem emoji trong DB và Sheet"""
    try:
        import gspread
        import os
        import json
        from oauth2client.service_account import ServiceAccountCredentials
        
        # Lấy data từ DB
        db = SessionLocal()
        db_employees = db.query(Employee).all()
        db_data = [{"tg_id": e.telegram_id, "name": e.name, "emoji": e.emoji} for e in db_employees]
        db.close()
        
        # Lấy data từ Sheet
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        service_account_info = os.environ.get("GOOGLE_SERVICE_ACCOUNT")
        
        sheet_data = []
        if service_account_info:
            creds_dict = json.loads(service_account_info)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            spreadsheet = client.open("ITADA REVIEW MAP")
            sheet = spreadsheet.worksheet("NHANVIEN")
            records = sheet.get_all_records()
            sheet_data = [{"tg_id": str(r.get("Telegram_ID", "")), "name": r.get("Tên", ""), "emoji": r.get("Emoji", "")} for r in records]
        
        return {
            "database": db_data,
            "sheet": sheet_data
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/list_review_logs")
def list_review_logs():
    """API xem danh sách review đã ghi nhận"""
    try:
        from database import ReviewLog
        db = SessionLocal()
        logs = db.query(ReviewLog).order_by(ReviewLog.id.desc()).limit(20).all()
        result = []
        for log in logs:
            result.append({
                "id": log.id,
                "google_review_id": log.google_review_id,
                "reviewer_name": log.reviewer_name,
                "stars": log.stars,
                "staff_id": log.staff_id,
                "status": log.status,
                "content": log.content[:50] + "..." if log.content and len(log.content) > 50 else log.content
            })
        db.close()
        return {"reviews": result}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/delete_review_log")
def delete_review_log(reviewer_name: str = None, review_id: int = None):
    """API xóa review log để cho phép quét lại
    
    Sử dụng:
    - /api/delete_review_log?reviewer_name=Tú Vlog
    - /api/delete_review_log?review_id=123
    """
    try:
        from database import ReviewLog
        db = SessionLocal()
        
        deleted = []
        
        if review_id:
            log = db.query(ReviewLog).filter(ReviewLog.id == review_id).first()
            if log:
                deleted.append({"id": log.id, "name": log.reviewer_name})
                db.delete(log)
        
        if reviewer_name:
            logs = db.query(ReviewLog).filter(ReviewLog.reviewer_name.contains(reviewer_name)).all()
            for log in logs:
                deleted.append({"id": log.id, "name": log.reviewer_name})
                db.delete(log)
        
        db.commit()
        db.close()
        
        if deleted:
            return {"success": True, "deleted": deleted, "message": f"Đã xóa {len(deleted)} review. Tool sẽ quét lại trong lần chạy tiếp theo."}
        else:
            return {"success": False, "message": "Không tìm thấy review nào để xóa"}
    except Exception as e:
        return {"success": False, "error": str(e)}
