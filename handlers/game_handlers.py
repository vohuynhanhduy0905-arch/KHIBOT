# --- FILE: handlers/game_handlers.py ---
# Xử lý các game: Tài Xỉu, Slot, PK, Kéo Búa Bao

import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import MAIN_GROUP_ID, GAME_TOPIC_ID, KBB_CHOICES, KBB_RULES
from database import SessionLocal, Employee
from handlers.user_handlers import check_private

# Lưu trận đấu đang diễn ra
ACTIVE_PK_MATCHES = {}
ACTIVE_KBB_MATCHES = {}


# ==========================================
# MENU GAME CHÍNH
# ==========================================

async def game_ui_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị menu game chính"""
    if not await check_private(update, context): 
        return
    
    user = update.effective_user
    msg = f"🎰 <b>TRUNG TÂM GIẢI TRÍ</b> 🎰\nChào <b>{user.full_name}</b>, đại gia muốn chơi gì?"
    keyboard = [
        [
            InlineKeyboardButton("🎲 Tài Xỉu", callback_data="menu_tx"),
            InlineKeyboardButton("🎰 Slot", callback_data="slot_menu")
        ],
        [
            InlineKeyboardButton("🥊 PK Xúc Xắc", callback_data="menu_pk"),
            InlineKeyboardButton("✂️ Kéo Búa Bao", callback_data="kbb_menu")
        ],
        [InlineKeyboardButton("❌ Đóng", callback_data="close_menu")]
    ]
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


# ==========================================
# SLOT MACHINE
# ==========================================

async def slot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị menu Slot Machine"""
    if not await check_private(update, context): 
        return
    
    txt = (
        "🎰 <b>SLOT MACHINE</b> 🎰\n"
        "━━━━━━━━━━━━━━━━\n"
        "🎯 Cách chơi: Quay và chờ kết quả!\n"
        "💎💎💎 = x50 (Jackpot)\n"
        "⭐⭐⭐ = x20\n"
        "🍇🍇🍇 = x10\n"
        "2️⃣ trùng = x1.5\n"
        "━━━━━━━━━━━━━━━━\n"
        "🪙 Chọn mức cược:"
    )
    
    kb = [
        [
            InlineKeyboardButton("5k", callback_data="slot_play_5000"),
            InlineKeyboardButton("10k", callback_data="slot_play_10000"),
            InlineKeyboardButton("20k", callback_data="slot_play_20000"),
            InlineKeyboardButton("50k", callback_data="slot_play_50000")
        ],
        [InlineKeyboardButton("🔙 Quay lại", callback_data="back_home")]
    ]
    
    await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")


async def handle_slot_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback handler cho slot_menu"""
    query = update.callback_query
    
    txt = (
        "🎰 <b>SLOT MACHINE</b> 🎰\n"
        "━━━━━━━━━━━━━━━━\n"
        "🎯 Cách chơi: Quay và chờ kết quả!\n"
        "💎💎💎 = x50 (Jackpot)\n"
        "⭐⭐⭐ = x20\n"
        "🍇🍇🍇 = x10\n"
        "2️⃣ trùng = x1.5\n"
        "━━━━━━━━━━━━━━━━\n"
        "🪙 Chọn mức cược:"
    )
    
    kb = [
        [
            InlineKeyboardButton("5k", callback_data="slot_play_5000"),
            InlineKeyboardButton("10k", callback_data="slot_play_10000"),
            InlineKeyboardButton("20k", callback_data="slot_play_20000"),
            InlineKeyboardButton("50k", callback_data="slot_play_50000")
        ],
        [InlineKeyboardButton("🔙 Quay lại", callback_data="back_home")]
    ]
    
    await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")


async def handle_slot_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi chơi Slot - CÓ ANIMATION"""
    query = update.callback_query
    user = query.from_user
    data = query.data
    
    amount = int(data.replace("slot_play_", ""))
    
    db = SessionLocal()
    emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
    
    if not emp or emp.coin < amount:
        await query.answer("💸 Không đủ Xu!", show_alert=True)
        db.close()
        return
    
    emp.coin -= amount
    db.commit()
    current_coin = emp.coin
    db.close()
    
    try:
        await query.message.delete()
    except:
        pass
    
    wait_msg = await context.bot.send_message(
        chat_id=user.id,
        text=f"🎰 Đang quay... (Cược: {amount:,.0f} Xu)"
    )
    
    dice_msg = await context.bot.send_dice(chat_id=user.id, emoji="🎰")
    slot_value = dice_msg.dice.value
    
    await asyncio.sleep(3)
    
    # Tính kết quả
    winnings = 0
    if slot_value == 64:
        winnings = amount * 50
        note = "🎉🎉🎉 <b>JACKPOT 777!</b> x50"
    elif slot_value == 43:
        winnings = amount * 20
        note = "🎊 <b>TRÙNG 3!</b> x20"
    elif slot_value in [1, 22]:
        winnings = amount * 10
        note = "✨ <b>TRÙNG 3!</b> x10"
    elif slot_value in [2, 3, 4, 6, 11, 16, 17, 21, 32, 33, 38, 41, 42, 48, 49, 54, 59, 61, 62, 63]:
        winnings = int(amount * 1.5)
        note = "👍 Trùng 2! x1.5"
    else:
        note = "😢 Không trúng!"
    
    db = SessionLocal()
    emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
    if winnings > 0:
        emp.coin += winnings
    db.commit()
    final_coin = emp.coin
    db.close()
    
    profit = winnings - amount
    profit_str = f"+{profit:,.0f}" if profit > 0 else f"{profit:,.0f}"
    
    try:
        await wait_msg.delete()
    except:
        pass
    
    result_msg = (
        f"🎰 <b>KẾT QUẢ SLOT</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"{note}\n"
        f"💰 {profit_str} Xu\n"
        f"🪙 Xu hiện có: <b>{final_coin:,.0f}</b>"
    )
    
    kb = [
        [
            InlineKeyboardButton("🔄 Quay tiếp", callback_data=f"slot_play_{amount}"),
            InlineKeyboardButton("💰 Đổi mức", callback_data="slot_menu")
        ],
        [InlineKeyboardButton("🔙 Menu Game", callback_data="back_home")]
    ]
    
    await context.bot.send_message(
        chat_id=user.id,
        text=result_msg,
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="HTML"
    )


# ==========================================
# KÉO BÚA BAO (PvP)
# ==========================================

async def kbb_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị menu Kéo Búa Bao"""
    if not await check_private(update, context): 
        return
    
    txt = (
        "✂️ <b>KÉO BÚA BAO</b> ✊\n"
        "━━━━━━━━━━━━━━━━\n"
        "Tạo kèo thách đấu, chờ người nhận!\n"
        "Cả 2 chọn bí mật, reveal cùng lúc.\n"
        "━━━━━━━━━━━━━━━━\n"
        "🪙 Chọn mức cược:"
    )
    
    kb = [
        [
            InlineKeyboardButton("10k Xu", callback_data="kbb_create_10000"),
            InlineKeyboardButton("20k Xu", callback_data="kbb_create_20000")
        ],
        [
            InlineKeyboardButton("50k Xu", callback_data="kbb_create_50000"),
            InlineKeyboardButton("100k Xu", callback_data="kbb_create_100000")
        ],
        [InlineKeyboardButton("🔙 Quay lại", callback_data="back_home")]
    ]
    
    await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")


async def handle_kbb_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tạo kèo Kéo Búa Bao"""
    query = update.callback_query
    user = query.from_user
    data = query.data
    
    amount = int(data.replace("kbb_create_", ""))
    
    db = SessionLocal()
    emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
    
    if not emp or emp.coin < amount:
        await query.answer("💸 Không đủ Xu!", show_alert=True)
        db.close()
        return
    
    emp_name = emp.name
    db.close()
    
    await query.edit_message_text(f"✅ Đã gửi thách đấu <b>{amount:,.0f} Xu</b> vào nhóm!", parse_mode="HTML")
    
    msg_content = (
        f"✂️ <b>KÉO BÚA BAO</b> ✊\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"👤 <b>{emp_name}</b> thách đấu!\n"
        f"🪙 Cược: <b>{amount:,.0f} Xu</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"👇 Ai dám nhận?"
    )
    
    kb = [[InlineKeyboardButton("✊ NHẬN KÈO", callback_data="kbb_join")]]
    
    try:
        sent_msg = await context.bot.send_message(
            chat_id=MAIN_GROUP_ID,
            message_thread_id=GAME_TOPIC_ID,
            text=msg_content,
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="HTML"
        )
        
        ACTIVE_KBB_MATCHES[sent_msg.message_id] = {
            "creator_id": str(user.id),
            "creator_name": emp_name,
            "amount": amount,
            "creator_choice": None,
            "joiner_id": None,
            "joiner_name": None,
            "joiner_choice": None
        }
    except Exception as e:
        await context.bot.send_message(user.id, f"⚠️ Lỗi: {e}")


async def handle_kbb_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Nhận kèo Kéo Búa Bao"""
    query = update.callback_query
    user = query.from_user
    msg_id = query.message.message_id
    
    match = ACTIVE_KBB_MATCHES.get(msg_id)
    if not match:
        await query.answer("❌ Kèo đã hết hạn!", show_alert=True)
        return
    
    if match["joiner_id"]:
        await query.answer("❌ Đã có người nhận rồi!", show_alert=True)
        return
    
    if str(user.id) == match["creator_id"]:
        await query.answer("🚫 Không thể tự chơi với mình!", show_alert=True)
        return
    
    db = SessionLocal()
    joiner = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
    
    if not joiner or joiner.coin < match["amount"]:
        await query.answer("💸 Không đủ Xu!", show_alert=True)
        db.close()
        return
    
    joiner_name = joiner.name
    db.close()
    
    match["joiner_id"] = str(user.id)
    match["joiner_name"] = joiner_name
    
    txt = (
        f"✂️ <b>KÉO BÚA BAO</b> ✊\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"👤 {match['creator_name']} ⚔️ {joiner_name}\n"
        f"🪙 Cược: <b>{match['amount']:,.0f} Xu</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"⏳ Đang chờ cả 2 chọn..."
    )
    
    await query.edit_message_text(txt, parse_mode="HTML")
    
    choice_kb = [
        [
            InlineKeyboardButton("✊ Búa", callback_data=f"kbb_choose_rock_{msg_id}"),
            InlineKeyboardButton("✋ Bao", callback_data=f"kbb_choose_paper_{msg_id}"),
            InlineKeyboardButton("✌️ Kéo", callback_data=f"kbb_choose_scissors_{msg_id}")
        ]
    ]
    
    choose_txt1 = f"✂️ <b>CHỌN VŨ KHÍ</b>\n\n⚔️ Trận với <b>{joiner_name}</b>\n🪙 Cược: {match['amount']:,.0f} Xu"
    choose_txt2 = f"✂️ <b>CHỌN VŨ KHÍ</b>\n\n⚔️ Trận với <b>{match['creator_name']}</b>\n🪙 Cược: {match['amount']:,.0f} Xu"
    
    try:
        await context.bot.send_message(
            chat_id=match["creator_id"],
            text=choose_txt1,
            reply_markup=InlineKeyboardMarkup(choice_kb),
            parse_mode="HTML"
        )
        await context.bot.send_message(
            chat_id=match["joiner_id"],
            text=choose_txt2,
            reply_markup=InlineKeyboardMarkup(choice_kb),
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Lỗi gửi tin chọn KBB: {e}")
    
    await query.answer("✅ Đã nhận kèo! Check tin nhắn riêng để chọn!")


async def handle_kbb_choose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi người chơi chọn Kéo/Búa/Bao"""
    query = update.callback_query
    user = query.from_user
    data = query.data
    
    parts = data.split("_")
    choice = f"kbb_{parts[2]}"
    msg_id = int(parts[3])
    
    match = ACTIVE_KBB_MATCHES.get(msg_id)
    if not match:
        await query.answer("❌ Trận đấu đã kết thúc!", show_alert=True)
        return
    
    user_id = str(user.id)
    choice_emoji, choice_name = KBB_CHOICES[choice]
    
    if user_id == match["creator_id"]:
        if match["creator_choice"]:
            await query.answer("⚠️ Bạn đã chọn rồi!", show_alert=True)
            return
        match["creator_choice"] = choice
        await query.edit_message_text(f"✅ Bạn đã chọn <b>{choice_emoji} {choice_name}</b>\n\n⏳ Chờ đối thủ...", parse_mode="HTML")
    elif user_id == match["joiner_id"]:
        if match["joiner_choice"]:
            await query.answer("⚠️ Bạn đã chọn rồi!", show_alert=True)
            return
        match["joiner_choice"] = choice
        await query.edit_message_text(f"✅ Bạn đã chọn <b>{choice_emoji} {choice_name}</b>\n\n⏳ Chờ đối thủ...", parse_mode="HTML")
    else:
        await query.answer("❌ Bạn không trong trận này!", show_alert=True)
        return
    
    if match["creator_choice"] and match["joiner_choice"]:
        await resolve_kbb_match(context, msg_id, match)


async def resolve_kbb_match(context: ContextTypes.DEFAULT_TYPE, msg_id: int, match: dict):
    """Xử lý kết quả trận đấu KBB"""
    c_choice = match["creator_choice"]
    j_choice = match["joiner_choice"]
    c_emoji, c_name = KBB_CHOICES[c_choice]
    j_emoji, j_name = KBB_CHOICES[j_choice]
    amount = match["amount"]
    
    if c_choice == j_choice:
        result = "🤝 HÒA!"
        winner = None
    elif KBB_RULES[c_choice] == j_choice:
        result = f"🏆 <b>{match['creator_name']}</b> THẮNG!"
        winner = "creator"
    else:
        result = f"🏆 <b>{match['joiner_name']}</b> THẮNG!"
        winner = "joiner"
    
    db = SessionLocal()
    creator = db.query(Employee).filter(Employee.telegram_id == match["creator_id"]).first()
    joiner = db.query(Employee).filter(Employee.telegram_id == match["joiner_id"]).first()
    
    if winner == "creator":
        creator.coin += amount
        joiner.coin -= amount
    elif winner == "joiner":
        joiner.coin += amount
        creator.coin -= amount
    
    db.commit()
    creator_coin = creator.coin
    joiner_coin = joiner.coin
    db.close()
    
    final_msg = (
        f"✂️ <b>KẾT QUẢ KÉO BÚA BAO</b> ✊\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"👤 {match['creator_name']}: {c_emoji}\n"
        f"👤 {match['joiner_name']}: {j_emoji}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"{result}\n"
        f"🪙 Cược: {amount:,.0f} Xu"
    )
    
    try:
        await context.bot.edit_message_text(
            chat_id=MAIN_GROUP_ID,
            message_id=msg_id,
            text=final_msg,
            parse_mode="HTML"
        )
    except:
        pass
    
    if winner == "creator":
        await context.bot.send_message(match["creator_id"], f"🎉 Bạn THẮNG! +{amount:,.0f} Xu\n🪙 Xu: {creator_coin:,.0f}")
        await context.bot.send_message(match["joiner_id"], f"😢 Bạn THUA! -{amount:,.0f} Xu\n🪙 Xu: {joiner_coin:,.0f}")
    elif winner == "joiner":
        await context.bot.send_message(match["joiner_id"], f"🎉 Bạn THẮNG! +{amount:,.0f} Xu\n🪙 Xu: {joiner_coin:,.0f}")
        await context.bot.send_message(match["creator_id"], f"😢 Bạn THUA! -{amount:,.0f} Xu\n🪙 Xu: {creator_coin:,.0f}")
    else:
        await context.bot.send_message(match["creator_id"], f"🤝 HÒA! Không ai mất Xu")
        await context.bot.send_message(match["joiner_id"], f"🤝 HÒA! Không ai mất Xu")
    
    del ACTIVE_KBB_MATCHES[msg_id]
