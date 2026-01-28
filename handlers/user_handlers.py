# --- FILE: handlers/user_handlers.py ---
# Xử lý các lệnh user: /start, /me, /qr, /diemdanh, /gift, /shop, /top
# ĐÃ SỬA: Đồng bộ emoji với Google Sheet - KHÔNG MẤT KHI DEPLOY

import io
import random
import asyncio
import time
from datetime import date, timedelta

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, ChatPermissions
)
from telegram.ext import ContextTypes

from config import (
    WEB_URL, ADMIN_ID, EMOJI_POOL, MAIN_GROUP_ID,
    DAILY_CHECKIN_REWARD, STREAK_7_BONUS
)
from database import SessionLocal, Employee, ShopLog
from staff_sheet import get_staff_by_telegram, register_staff, get_staff_emoji
from utils import (
    get_rank_info, get_random_gift, create_card_image, 
    generate_streak_display, SPAM_TRACKER
)


def get_main_menu():
    """Tạo menu chính"""
    keyboard = [
        ["💳 Ví & Thẻ", "📅 Điểm Danh"],
        ["🎰 Giải Trí", "🛒 Shop Xu"],
        [KeyboardButton("⚡ Order Nhanh", web_app=WebAppInfo(url=f"{WEB_URL}/order"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


# ==========================================
# CHECK PRIVATE - Chống spam trong group
# ==========================================

async def check_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kiểm tra chat riêng, chống spam trong group"""
    if update.effective_chat.type == "private":
        return True
    
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    try: 
        await update.message.delete()
    except: 
        pass
    
    user_id = user.id
    now = time.time()
    
    if user_id not in SPAM_TRACKER:
        SPAM_TRACKER[user_id] = []
    
    SPAM_TRACKER[user_id] = [t for t in SPAM_TRACKER[user_id] if now - t < 10]
    SPAM_TRACKER[user_id].append(now)
    
    if len(SPAM_TRACKER[user_id]) >= 3:
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=now + 300
            )
            msg = await context.bot.send_message(
                chat_id, 
                f"🚫 <b>{user.first_name}</b> spam quá nhiều! Bị cấm chat 5 phút.", 
                parse_mode="HTML"
            )
            SPAM_TRACKER[user_id] = []
            await asyncio.sleep(10)
            try: 
                await msg.delete()
            except: 
                pass
        except:
            msg = await context.bot.send_message(chat_id, f"⚠️ Đừng spam nữa {user.first_name}!")
            await asyncio.sleep(3)
            try: 
                await msg.delete()
            except: 
                pass
        return False

    if len(SPAM_TRACKER[user_id]) == 1:
        msg = await update.message.reply_text(f"🤫 {user.first_name}, qua nhắn riêng với Bot nhé!")
        await asyncio.sleep(5)
        try: 
            await msg.delete()
        except: 
            pass
    
    return False


# ==========================================
# /start - Khởi động bot
# EMOJI ĐƯỢC LƯU VÀO GOOGLE SHEET
# ==========================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /start - ĐỒNG BỘ VỚI GOOGLE SHEET"""
    if not await check_private(update, context): 
        return
    
    user = update.effective_user
    db = SessionLocal()
    
    try:
        # Kiểm tra trong database trước
        emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
        
        # Lấy emoji từ Google Sheet (nguồn chính)
        sheet_emoji = get_staff_emoji(str(user.id))
        
        if not emp:
            # Chưa có trong DB → Tạo mới
            # Lấy emoji từ Sheet nếu có, không thì tạo mới
            if sheet_emoji:
                emoji = sheet_emoji
            else:
                # Tạo emoji mới và lưu vào Sheet
                used_emojis = [e.emoji for e in db.query(Employee).all() if e.emoji]
                available = [e for e in EMOJI_POOL if e not in used_emojis]
                if not available:
                    available = EMOJI_POOL
                emoji = random.choice(available)
            
            emp = Employee(telegram_id=str(user.id), name=user.full_name, emoji=emoji)
            db.add(emp)
            db.commit()
            
            # Đồng bộ lên Google Sheet
            try:
                register_staff(user.full_name, "", str(user.id))
            except Exception as e:
                print(f"Lỗi đồng bộ Sheet: {e}")
        else:
            # Đã có trong DB → Đồng bộ emoji từ Sheet
            if sheet_emoji and sheet_emoji != emp.emoji:
                # Sheet có emoji khác → cập nhật DB theo Sheet
                emp.emoji = sheet_emoji
                db.commit()
            elif not sheet_emoji and emp.emoji:
                # Sheet chưa có → đồng bộ từ DB lên Sheet
                try:
                    register_staff(emp.name, "", str(user.id))
                except Exception as e:
                    print(f"Lỗi đồng bộ Sheet: {e}")
        
        # Lấy emoji cuối cùng (ưu tiên Sheet)
        final_emoji = sheet_emoji if sheet_emoji else emp.emoji
        
        msg = (
            f"Chào <b>{emp.name}</b> {final_emoji}!\n"
            f"Chúc một ngày làm việc năng suất.\n"
            f"👇 <i>Chọn menu bên dưới:</i>"
        )
        await update.message.reply_text(msg, reply_markup=get_main_menu(), parse_mode="HTML")
        
    except Exception as e:
        print(f"Lỗi start_command: {e}")
        await update.message.reply_text("Có lỗi xảy ra! Vui lòng thử lại.")
    finally:
        db.close()


# ==========================================
# /me - Xem thẻ nhân viên (FORMAT ĐẸP)
# ==========================================

async def me_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /me - Xem thẻ nhân viên"""
    if not await check_private(update, context): 
        return
    
    user = update.effective_user
    db = SessionLocal()
    emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
    
    if emp:
        # Lấy emoji từ Sheet (ưu tiên)
        sheet_emoji = get_staff_emoji(str(user.id))
        emoji = sheet_emoji if sheet_emoji else emp.emoji
        
        wait_msg = await update.message.reply_text("📸 Đợi cái ní, đang lấy avt để in thẻ...")
        
        try:
            # Lấy avatar
            photos = await context.bot.get_user_profile_photos(user.id, limit=1)
            avatar_bytes = None
            if photos.total_count > 0:
                file = await context.bot.get_file(photos.photos[0][0].file_id)
                avatar_data = await file.download_as_bytearray()
                avatar_bytes = io.BytesIO(avatar_data)
            
            # Tạo thẻ
            rank_name, rank_icon = get_rank_info(emp.coin)
            card_bytes = create_card_image(
                name=emp.name,
                emoji=emoji,
                rank_name=rank_name,
                rank_icon=rank_icon,
                balance=emp.balance,
                coin=emp.coin,
                avatar_bytes=avatar_bytes
            )
            
            await wait_msg.delete()
            
            # Caption
            caption = (
                f"<b>🎴 THẺ NHÂN VIÊN</b>\n\n"
                f"👤 <b>{emp.name}</b> {emoji}\n"
                f"🏅 Cấp bậc: {rank_icon} {rank_name}\n"
                f"💵 Lương: <b>{emp.balance:,.0f}đ</b>\n"
                f"🪙 Xu game: <b>{emp.coin:,.0f} xu</b>\n\n"
                f"<i>💡 Gõ /diemdanh để nhận Xu mỗi ngày!</i>"
            )
            
            await update.message.reply_photo(
                photo=card_bytes,
                caption=caption,
                parse_mode="HTML"
            )
        except Exception as e:
            await wait_msg.edit_text(f"❌ Lỗi tạo thẻ: {e}")
    else:
        await update.message.reply_text("⚠️ Bạn chưa đăng ký! Gõ /start")
    
    db.close()



# ==========================================
# /qr - Tạo mã QR cho nhân viên
# ==========================================

async def qr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tạo mã QR để khách quét đánh giá"""
    if not await check_private(update, context): 
        return
    
    user_id = str(update.effective_user.id)
    link = f"{WEB_URL}/?ref={user_id}"
    qr_api = f"https://api.qrserver.com/v1/create-qr-code/?size=500x500&data={link}"
    
    await update.message.reply_photo(
        photo=qr_api, 
        caption="🚀 <b>Mã QR Tốc Độ Cao</b>\nĐưa khách quét ngay!",
        parse_mode="HTML"
    )


# ==========================================
# /top - Bảng xếp hạng (FORMAT ĐẸP)
# ==========================================

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị bảng xếp hạng"""
    if not await check_private(update, context): 
        return
    
    db = SessionLocal()
    
    from sqlalchemy import desc
    top_balance = db.query(Employee).order_by(desc(Employee.balance)).limit(5).all()
    top_coin = db.query(Employee).order_by(desc(Employee.coin)).limit(5).all()
    
    msg = "🏆 <b>BẢNG PHONG THẦN</b> 🏆\n\n"
    
    msg += "💰 <b>TOP ĐẠI GIA (Lương):</b>\n"
    for i, emp in enumerate(top_balance, 1):
        msg += f"{i}. {emp.name}: {emp.balance:,.0f}đ\n"
        
    msg += "\n🪙 <b>TOP CON BẠC (Xu):</b>\n"
    for i, emp in enumerate(top_coin, 1):
        msg += f"{i}. {emp.name}: {emp.coin:,.0f} Xu\n"
        
    await update.message.reply_text(msg, parse_mode="HTML")
    db.close()


# ==========================================
# /diemdanh - Điểm danh (có streak)
# ==========================================

async def daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Điểm danh hàng ngày với streak bonus"""
    if not await check_private(update, context): 
        return
    
    user = update.effective_user
    db = SessionLocal()
    emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
    
    if not emp:
        await update.message.reply_text("❌ Bạn chưa được đăng ký trong hệ thống!")
        db.close()
        return
    
    today = date.today()
    
    if emp.last_checkin == today:
        streak_display = generate_streak_display(emp.checkin_streak)
        await update.message.reply_text(
            f"⚠️ Bạn đã điểm danh hôm nay rồi!\n"
            f"🔥 Streak hiện tại: {emp.checkin_streak} ngày\n"
            f"📊 Tuần này: {streak_display}\n"
            f"📅 Quay lại vào ngày mai nhé!"
        )
        db.close()
        return
    
    yesterday = today - timedelta(days=1)
    
    if emp.last_checkin == yesterday:
        emp.checkin_streak += 1
    else:
        emp.checkin_streak = 1
    
    base_reward = DAILY_CHECKIN_REWARD
    bonus = 0
    bonus_text = ""
    
    if emp.checkin_streak >= 7 and emp.checkin_streak % 7 == 0:
        bonus = STREAK_7_BONUS
        bonus_text = f"\n🎁 <b>BONUS 7 NGÀY: +{bonus:,.0f} Xu!</b>"
    
    total_reward = base_reward + bonus
    emp.coin += total_reward
    emp.last_checkin = today
    db.commit()
    
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
    db.close()


# ==========================================
# /gift - Hộp quà may mắn
# ==========================================

async def gift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mở hộp quà may mắn - FREE 1 lần/ngày"""
    if not await check_private(update, context): 
        return
    
    user = update.effective_user
    db = SessionLocal()
    emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
    
    if not emp:
        await update.message.reply_text("❌ Bạn chưa được đăng ký trong hệ thống!")
        db.close()
        return
    
    today = date.today()
    
    if emp.last_gift_open == today:
        await update.message.reply_text(
            f"🎁 Bạn đã mở quà hôm nay rồi!\n"
            f"📅 Quay lại vào ngày mai nhé!"
        )
        db.close()
        return
    
    reward = get_random_gift()
    emp.coin += reward
    emp.last_gift_open = today
    db.commit()
    
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
    db.close()


# ==========================================
# /shop - Shop đổi quà
# ==========================================

async def shop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị shop đổi quà"""
    if not await check_private(update, context): 
        return
    
    user = update.effective_user
    db = SessionLocal()
    emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
    
    if not emp:
        await update.message.reply_text("❌ Bạn chưa đăng ký!")
        db.close()
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
    db.close()
