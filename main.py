# --- FILE: main.py ---
# Bot Trà Sữa Khỉ - Phiên bản tối ưu với modules

import asyncio
import random
from datetime import datetime, timedelta
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
    MORNING_MESSAGES, EVENING_MESSAGES
)
from database import init_db, SessionLocal, Employee, Review, ShopLog
from staff_sheet import get_staff_by_pin

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
templates = Jinja2Templates(directory="templates")
bot_app = Application.builder().token(TOKEN).build()

# Lưu tin nhắn thông báo: {message_id: set(user_ids đã nhận Xu)}
DAILY_ANNOUNCEMENT_MSG = {}

# Reward cho reaction
REACTION_REWARD = 10000


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
            [InlineKeyboardButton("🎲 Tài Xỉu", callback_data="menu_tx"), InlineKeyboardButton("🎰 Slot", callback_data="slot_menu")],
            [InlineKeyboardButton("🥊 PK Xúc Xắc", callback_data="menu_pk"), InlineKeyboardButton("✂️ Kéo Búa Bao", callback_data="kbb_menu")],
            [InlineKeyboardButton("❌ Đóng", callback_data="close_menu")]
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return
    
    if data == "menu_tx":
        if chat_type != "private":
            await query.answer("🎲 Vào chat riêng với Bot để chơi!", show_alert=True)
            return
        txt = "🎲 <b>TÀI XỈU SIÊU TỐC</b>\n━━━━━━━━━━━━━━━━\n🔴 <b>XỈU:</b> 3 - 10 điểm\n🔵 <b>TÀI:</b> 11 - 18 điểm\n⚡ <b>Tỉ lệ ăn:</b> 1 ăn 0.85\n⚠️ <b>Bão (3 số giống nhau):</b> Nhà cái ăn hết!"
        kb = [[InlineKeyboardButton("🔴 Đặt XỈU", callback_data="tx_chon_xiu"), InlineKeyboardButton("🔵 Đặt TÀI", callback_data="tx_chon_tai")], [InlineKeyboardButton("🔙 Quay lại", callback_data="back_home")]]
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
    
    if data.startswith("tx_bet_"):
        parts = data.split("_")
        choice, amount = parts[2], int(parts[3])
        db = SessionLocal()
        emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
        if not emp or emp.coin < amount:
            await query.answer("💸 Không đủ Xu!", show_alert=True)
            db.close()
            return
        emp.coin -= amount
        db.commit()
        db.close()
        try:
            await query.message.delete()
        except:
            pass
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
            winnings = int(amount * 1.85)
            result = f"🎉 THẮNG! +{winnings - amount:,.0f} Xu"
        else:
            result = f"😢 THUA! -{amount:,.0f} Xu"
        db = SessionLocal()
        emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
        if winnings > 0:
            emp.coin += winnings
        db.commit()
        final_coin = emp.coin
        db.close()
        result_type = "XỈU" if result_is_xiu else "TÀI"
        msg = f"🎲 <b>KẾT QUẢ TÀI XỈU</b>\n━━━━━━━━━━━━━━━━\n🎯 Bạn đặt: {'🔴 XỈU' if choice == 'xiu' else '🔵 TÀI'}\n🎲 Kết quả: {dice1} + {dice2} + {dice3} = {total} ({result_type})\n━━━━━━━━━━━━━━━━\n{result}\n🪙 Xu hiện có: <b>{final_coin:,.0f}</b>"
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
    asyncio.create_task(bot_app.updater.start_polling())
    asyncio.create_task(run_announcement_scheduler())
    print("✅ Bot đã khởi động với Menu chuẩn...")
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
        "Trà sữa thơm béo, topping siêu nhiều luôn. 10 điểm!",
        "Quán decor xinh, nước ngon, nhân viên dễ thương.",
        "Trà trái cây tươi mát, uống là nghiền. Sẽ quay lại!",
        "Nước ngon, ship nhanh, nhân viên nhiệt tình. 5 sao!",
        "Trà sữa đậm vị, trân châu dẻo. Sẽ ghé lại!"
    ])
    return {"content": content}
