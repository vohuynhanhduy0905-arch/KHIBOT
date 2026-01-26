# --- FILE: handlers/user_handlers.py ---
# Xử lý các lệnh cơ bản của user: /start, /me, /diemdanh, /gift, /shop

import io
import random
from datetime import date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from telegram.ext import ContextTypes

from config import (
    WEB_URL, ADMIN_ID, EMOJI_POOL,
    DAILY_CHECKIN_REWARD, STREAK_7_BONUS
)
from database import SessionLocal, Employee, ShopLog
from utils import (
    get_db, log_info, log_user_action, log_error_with_context,
    get_rank_info, get_random_gift, create_card_image, generate_streak_display
)


def get_main_menu():
    """Tạo menu chính"""
    keyboard = [
        ["💳 Ví & Thẻ", "📅 Điểm Danh"],
        ["🎰 Giải Trí", "🛒 Shop Xu"],
        [KeyboardButton("⚡ Order Nhanh (Vào Nhóm)", web_app=WebAppInfo(url=f"{WEB_URL}/webapp"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


# ==========================================
# /start - Khởi động bot
# ==========================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /start"""
    user = update.effective_user
    log_user_action(str(user.id), user.full_name, "START")
    
    with get_db() as db:
        emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
        
        if not emp:
            # Tạo nhân viên mới
            used_emojis = [e.emoji for e in db.query(Employee.emoji).all()]
            available = [e for e in EMOJI_POOL if e not in used_emojis]
            new_emoji = random.choice(available) if available else random.choice(EMOJI_POOL)
            
            emp = Employee(
                telegram_id=str(user.id),
                name=user.full_name,
                emoji=new_emoji,
                balance=0,
                coin=50000  # Tặng 50k Xu khởi đầu
            )
            db.add(emp)
            db.commit()
            
            log_info(f"Tạo nhân viên mới: {user.full_name} ({user.id})")
            
            await update.message.reply_text(
                f"🎉 <b>CHÀO MỪNG {user.full_name.upper()}!</b>\n\n"
                f"Bạn đã được đăng ký với emoji: {new_emoji}\n"
                f"🎁 Tặng bạn <b>50,000 Xu</b> để chơi game!\n\n"
                f"Dùng /me để xem thẻ nhân viên.",
                reply_markup=get_main_menu(),
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                f"👋 Chào <b>{emp.name}</b>!\n\n"
                f"💰 Ví: {emp.balance:,.0f}đ\n"
                f"🪙 Xu: {emp.coin:,.0f}",
                reply_markup=get_main_menu(),
                parse_mode="HTML"
            )


# ==========================================
# /me - Xem thẻ nhân viên
# ==========================================

async def me_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /me - Xem thẻ nhân viên"""
    user = update.effective_user
    
    with get_db() as db:
        emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
        
        if not emp:
            await update.message.reply_text("❌ Bạn chưa đăng ký! Gõ /start để bắt đầu.")
            return
        
        # Lấy avatar
        avatar_bytes = None
        try:
            photos = await context.bot.get_user_profile_photos(user.id, limit=1)
            if photos.total_count > 0:
                file = await context.bot.get_file(photos.photos[0][0].file_id)
                avatar_bytes = io.BytesIO()
                await file.download_to_memory(avatar_bytes)
                avatar_bytes.seek(0)
        except:
            pass
        
        # Tạo thẻ
        card = create_card_image(emp.name, emp.emoji, emp.balance, emp.coin, avatar_bytes)
        
        rank_name, rank_icon = get_rank_info(emp.balance)
        caption = f"{rank_icon} <b>{emp.name}</b> | {rank_name}"
        
        await update.message.reply_photo(photo=card, caption=caption, parse_mode="HTML")


# ==========================================
# /diemdanh - Điểm danh hàng ngày (có streak)
# ==========================================

async def daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Điểm danh hàng ngày với streak bonus"""
    user = update.effective_user
    
    with get_db() as db:
        emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
        
        if not emp:
            await update.message.reply_text("❌ Bạn chưa được đăng ký trong hệ thống!")
            return
        
        today = date.today()
        
        # Kiểm tra đã điểm danh hôm nay chưa
        if emp.last_checkin == today:
            streak_display = generate_streak_display(emp.checkin_streak)
            await update.message.reply_text(
                f"⚠️ Bạn đã điểm danh hôm nay rồi!\n"
                f"🔥 Streak hiện tại: {emp.checkin_streak} ngày\n"
                f"📊 Tuần này: {streak_display}\n"
                f"📅 Quay lại vào ngày mai nhé!"
            )
            return
        
        # Tính streak
        yesterday = today - timedelta(days=1)
        
        if emp.last_checkin == yesterday:
            emp.checkin_streak += 1
        else:
            emp.checkin_streak = 1
        
        # Thưởng cơ bản
        base_reward = DAILY_CHECKIN_REWARD
        bonus = 0
        bonus_text = ""
        
        # Bonus streak 7 ngày
        if emp.checkin_streak >= 7 and emp.checkin_streak % 7 == 0:
            bonus = STREAK_7_BONUS
            bonus_text = f"\n🎁 <b>BONUS 7 NGÀY: +{bonus:,.0f} Xu!</b>"
        
        total_reward = base_reward + bonus
        emp.coin += total_reward
        emp.last_checkin = today
        
        db.commit()
        
        log_user_action(str(user.id), user.full_name, "ĐIỂM DANH", f"Streak: {emp.checkin_streak}, +{total_reward} Xu")
        
        streak_display = generate_streak_display(emp.checkin_streak)
        
        msg = (
            f"📅 <b>ĐIỂM DANH THÀNH CÔNG!</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"💰 +{base_reward:,.0f} Xu{bonus_text}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"🔥 Streak: <b>{emp.checkin_streak} ngày</b>\n"
            f"📊 Tuần này: {streak_display}\n"
            f"🪙 Xu hiện có: <b>{emp.coin:,.0f}</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"💡 Điểm danh 7 ngày liên tục = +{STREAK_7_BONUS:,} Xu!"
        )
        
        await update.message.reply_text(msg, parse_mode="HTML")


# ==========================================
# /gift - Hộp quà may mắn
# ==========================================

async def gift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mở hộp quà may mắn - FREE 1 lần/ngày"""
    user = update.effective_user
    
    with get_db() as db:
        emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
        
        if not emp:
            await update.message.reply_text("❌ Bạn chưa được đăng ký trong hệ thống!")
            return
        
        today = date.today()
        
        # Kiểm tra đã mở quà hôm nay chưa
        if emp.last_gift_open == today:
            await update.message.reply_text(
                f"🎁 Bạn đã mở quà hôm nay rồi!\n"
                f"📅 Quay lại vào ngày mai nhé!"
            )
            return
        
        # Random phần thưởng
        reward = get_random_gift()
        
        # Cập nhật
        emp.coin += reward
        emp.last_gift_open = today
        db.commit()
        
        log_user_action(str(user.id), user.full_name, "MỞ QUÀ", f"+{reward} Xu")
        
        # Hiệu ứng
        if reward >= 20000:
            effect = "🎉🎊🎉 SIÊU HIẾM! 🎉🎊🎉"
            emoji = "💎"
        elif reward >= 15000:
            effect = "✨ HIẾM! ✨"
            emoji = "🌟"
        elif reward >= 10000:
            effect = "🎊 Tốt lắm!"
            emoji = "🎁"
        else:
            effect = "👍 Không tệ!"
            emoji = "📦"
        
        msg = (
            f"🎁 <b>HỘP QUÀ MAY MẮN</b> 🎁\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"{emoji} Mở hộp...\n\n"
            f"{effect}\n"
            f"💰 <b>+{reward:,.0f} Xu!</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"🪙 Xu hiện có: <b>{emp.coin:,.0f}</b>\n\n"
            f"📅 Quay lại ngày mai để mở tiếp!"
        )
        
        await update.message.reply_text(msg, parse_mode="HTML")


# ==========================================
# /shop - Shop đổi quà
# ==========================================

async def shop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị shop đổi quà"""
    user = update.effective_user
    
    with get_db() as db:
        emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
        
        if not emp:
            await update.message.reply_text("❌ Bạn chưa đăng ký!")
            return
        
        txt = (
            f"🛒 <b>SHOP ĐỔI XU</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"🪙 Xu hiện có: <b>{emp.coin:,.0f}</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"💵 Quy đổi Xu → Lương:\n"
            f"(Tỷ lệ: 100 Xu = 1đ)"
        )
        
        kb = [
            [
                InlineKeyboardButton("1,000đ (100k Xu)", callback_data="buy_salary_1000"),
                InlineKeyboardButton("2,000đ (200k Xu)", callback_data="buy_salary_2000")
            ],
            [
                InlineKeyboardButton("5,000đ (500k Xu)", callback_data="buy_salary_5000"),
                InlineKeyboardButton("10,000đ (1M Xu)", callback_data="buy_salary_10000")
            ],
            [InlineKeyboardButton("❌ Đóng", callback_data="close_menu")]
        ]
        
        await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
