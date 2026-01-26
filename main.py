import os
import random
import asyncio
import io
import time
import json
from staff_sheet import (
    get_staff_by_pin, 
    get_staff_by_telegram, 
    get_staff_by_phone,
    register_staff, 
    delete_staff, 
    get_all_staff,
    get_staff_count
)
from pydantic import BaseModel
from typing import List, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
# --- CẬP NHẬT IMPORT (Dòng 8-15) ---
# --- TÌM ĐOẠN IMPORT TƯƠNG TỰ VÀ THAY THẾ ---
from telegram import (
    Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, BotCommand, 
    InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions, WebAppInfo,
    KeyboardButton # <--- QUAN TRỌNG: Phải có cái này mới tạo nút Web App được
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes, 
    CallbackQueryHandler # <--- MỚI
)
# --- TÌM DÒNG IMPORT DATABASE VÀ SỬA THÀNH ---
from database import SessionLocal, Employee, ReviewLog, Review, init_db, ShopLog # <--- Thêm ShopLog
from datetime import datetime, date, timedelta  # Thêm timedelta
from sqlalchemy import desc
from sqlalchemy.sql import func  
from PIL import Image, ImageDraw, ImageFont

# --- CẤU HÌNH ---
TOKEN = os.environ.get("TELEGRAM_TOKEN") 
ADMIN_ID = "1587932557"
WEB_URL = "https://trasuakhi.onrender.com" 
MAIN_GROUP_ID = -1003566594243
ORDER_TOPIC_ID = 180 # Thay 123 bằng Topic ID thực của bạn
GAME_TOPIC_ID = 181   # Topic cho game PK
CHAT_TOPIC_ID = 3
GROUP_INVITE_LINK = "https://t.me/c/3566594243/2"
SPAM_TRACKER = {}
DAILY_ANNOUNCEMENT_MSG = {}  # {message_id: set(user_ids đã react)}
ACTIVE_RPS_MATCHES = {} 

# Setup
init_db()
templates = Jinja2Templates(directory="templates")

# List Emoji (Dùng khi tạo NV mới)
EMOJI_POOL = [
    "🍇", "🍈", "🍉", "🍊", "🍋", "🍌", "🍍", "🥭", "🍎", "🍏", "🍐", "🍑", "🍒", "🍓", "🥝", "🍅", "🥥", 
    "🥑", "🍆", "🥔", "🥕", "🌽", "🌶️", "🥒", "🥬", "🥦", "🧄", "🧅", "🍄", "🥜", "🌰", "🍞", "🥐", "🥖", 
    "🥨", "🥯", "🥞", "🧇", "🧀", "🍖", "🍗", "🥩", "🥓", "🍔", "🍟", "🍕", "🌭", "🥪", "🌮", "🌯", "🥙", 
    "🧆", "🥚", "🍳", "🥘", "🍲", "🥣", "🥗", "🍿", "🧈", "🧂", "🥫", "🍱", "🍘", "🍙", "🍚", "🍛", "🍜", 
    "🍝", "🍠", "🍢", "🍣", "🍤", "🍥", "🥮", "🍡", "🥟", "🥠", "🥡", "🦀", "🦞", "🦐", "🦑", "🦪", "🍦", 
    "🍧", "🍨", "🍩", "🍪", "🎂", "🍰", "🧁", "🥧", "🍫", "🍬", "🍭", "🍮", "🍯", "🍼", "🥛", "☕", "🍵", 
    "🍶", "🍾", "🍷", "🍸", "🍹", "🍺", "🍻", "🥂", "🥃", "🥤", "🧃", "🧉", "🧊", "🥢", "🍽️", "🍴", "🥄"
]

# Hàm phụ để cắt ảnh thành hình tròn
def crop_to_circle(img):
    mask = Image.new('L', img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + img.size, fill=255)
    output = Image.new('RGBA', img.size, (0, 0, 0, 0))
    output.paste(img, (0, 0), mask)
    return output

# --- HÀM TÍNH RANK VÀ ICON ---
def get_rank_info(balance):
    name = "Dân Thường"
    icon = "🌱" 
    if balance >= 10000:  name, icon = "Kẻ Tập Sự", "🪵"
    if balance >= 30000:  name, icon = "Người Mới", "🥉"
    if balance >= 50000:  name, icon = "Tân Binh", "🥈"
    if balance >= 70000:  name, icon = "Kẻ Thách Thức", "⚔️"
    if balance >= 100000: name, icon = "Chiến Binh", "🛡️"
    if balance >= 150000: name, icon = "Cao Thủ", "🥋"
    if balance >= 200000: name, icon = "Đại Gia", "💎"
    if balance >= 300000: name, icon = "Bá Chủ", "👑"
    if balance >= 500000: name, icon = "Huyền Thoại", "👑🐉"
    return name, icon

## --- TÌM HÀM get_main_menu VÀ THAY THẾ TOÀN BỘ ---
def get_main_menu():
    keyboard = [
        ["💳 Ví & Thẻ", "📅 Điểm Danh"],
        ["🎰 Giải Trí", "🛒 Shop Xu"],
        # Dưới đây là cách viết đúng để nút mở lên Web App
        [KeyboardButton("⚡ Order Nhanh (Vào Nhóm)", web_app=WebAppInfo(url=f"{WEB_URL}/webapp"))] 
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- HÀM VẼ THẺ NHÂN VIÊN (ĐÃ SỬA LỖI) ---
def create_card_image(name, emoji, balance, coin, avatar_bytes=None):
    W, H = 800, 500
    
    # 1. Tạo nền
    try:
        img = Image.open("static/card_bg.jpg").convert("RGBA")
        img = img.resize((W, H))
    except:
        img = Image.new('RGBA', (W, H), color='#1A5336')

    draw = ImageDraw.Draw(img)

    # 2. Dán Logo (Góc phải trên)
    try:
        logo = Image.open("static/logo.png").convert("RGBA")
        logo_size = 110
        logo = logo.resize((logo_size, logo_size))
        logo = crop_to_circle(logo)
        img.paste(logo, (W - logo_size - 30, 30), logo)
    except: pass

    # 3. Dán Avatar (Giữa)
    if avatar_bytes:
        try:
            avatar = Image.open(avatar_bytes).convert("RGBA")
            avatar = avatar.resize((160, 160))
            avatar = crop_to_circle(avatar)
            # Viền vàng cho avatar
            draw.ellipse((W//2 - 82, 38, W//2 + 82, 202), outline="#F4D03F", width=3) 
            img.paste(avatar, (W//2 - 80, 40), avatar)
        except: pass

    try:
        font_name = ImageFont.truetype("static/font.ttf", 60) 
        font_rank = ImageFont.truetype("static/font.ttf", 30)
        font_money = ImageFont.truetype("static/font.ttf", 45) # Giảm size xíu để viết 2 dòng
    except:
        font_name = ImageFont.load_default()
        font_rank = ImageFont.load_default()
        font_money = ImageFont.load_default()

    # 5. Lấy tên Rank (Vẫn dùng balance để tính rank như yêu cầu)
    rank_name, _ = get_rank_info(balance)

    # 6. Căn giữa
    draw = ImageDraw.Draw(img) # Đảm bảo biến draw đã có
    def draw_centered(y, text, font, color):
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
        except:
            text_width = font.getlength(text)
        x = (W - text_width) / 2
        draw.text((x, y), text, font=font, fill=color)

    # 7. Viết chữ (Căn chỉnh lại toạ độ Y để nhét thêm dòng Xu)
    draw_centered(230, name, font_name, "white")
    draw_centered(300, f"{rank_name}", font_rank, "#F4D03F") 
    
    # Hiển thị 2 dòng tiền
    draw_centered(350, f"Ví: {balance:,.0f}đ", font_money, "white")
    draw_centered(410, f"Xu: {coin:,.0f}", font_money, "#00FF00") # Màu xanh lá cho Xu

    # 8. Xuất ảnh
    bio = io.BytesIO()
    bio.name = 'card.png'
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

# --- LOGIC GAME & NÚT BẤM ---
ACTIVE_PK_MATCHES = {} 

# --- HÀM HIỂN THỊ MENU GAME (ĐÃ BỔ SUNG LẠI) ---
async def game_ui_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type = update.effective_chat.type
    user = update.effective_user
    
    # 1. Nếu chat trong nhóm -> Xóa tin nhắn và cảnh báo nhẹ
    if chat_type != "private":
        try: await update.message.delete() # Xóa lệnh /game của user
        except: pass
        
        # Gửi cảnh báo tự xóa sau 5s
        msg = await update.message.reply_text(f"⚠️ {user.first_name} ơi, qua nhắn riêng với Bot để chơi nhé!")
        await asyncio.sleep(5)
        try: await msg.delete()
        except: pass
        return

    # 2. Nếu là chat riêng -> Hiện Menu
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

# --- HÀM XỬ LÝ NÚT BẤM (ĐÃ SỬA LỖI PK IM LẶNG) ---
async def handle_game_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data
    chat_type = query.message.chat.type 

    try:
        await query.answer()
    except: pass

    # --- NHÓM 1: ĐIỀU HƯỚNG ---
    if data == "close_menu":
        await query.delete_message()
        return

    if data == "back_home":
        # Quay lại menu game chính
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
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return

    if data == "menu_tx":
        if chat_type != "private":
            url = f"t.me/{context.bot.username}?start=game"
            await context.bot.send_message(chat_id=query.message.chat_id, text="⚠️ Game này qua nhắn riêng với Bot chơi nhé!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👉 Qua Bot", url=url)]]))
            return

        txt = (
            "🎲 <b>TÀI XỈU SIÊU TỐC</b>\n"
            "━━━━━━━━━━━━━━━━\n"
            "🔴 <b>XỈU:</b> 3 - 10 điểm\n"
            "🔵 <b>TÀI:</b> 11 - 18 điểm\n"
            "⚡ <b>Tỉ lệ ăn:</b> 1 ăn 0.85\n"
            "⚠️ <b>Bão (3 số giống nhau):</b> Nhà cái ăn hết!"
        )
        kb = [
            [
                InlineKeyboardButton("🔴 Đặt XỈU", callback_data="tx_chon_xiu"),
                InlineKeyboardButton("🔵 Đặt TÀI", callback_data="tx_chon_tai")
            ],
            [InlineKeyboardButton("🔙 Quay lại", callback_data="back_home")]
        ]
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return

    # --- SỬA LẠI ĐOẠN NÀY TRONG main.py ---
    if data == "menu_pk":
        # Không bắt ra nhóm nữa, cho hiện nút cược luôn tại đây
        txt = (
            "🥊 <b>SÀN ĐẤU PK 1vs1 (XU)</b>\n"
            "Chọn mức cược tại đây, Bot sẽ gửi lời mời vào Nhóm chung.\n"
            "👇 <b>Chọn mức thách đấu:</b>"
        )
        
        # Mức cược PK: 10k, 20k, 50k, 100k
        kb = [
            [
                InlineKeyboardButton("⚡ 10k Xu", callback_data="pk_create_10000"), 
                InlineKeyboardButton("⚡ 20k Xu", callback_data="pk_create_20000"), 
                InlineKeyboardButton("⚡ 50k Xu", callback_data="pk_create_50000"), 
                InlineKeyboardButton("⚡ 100k Xu", callback_data="pk_create_100000")
            ], 
            [InlineKeyboardButton("🔙 Quay lại", callback_data="back_home")]
        ]
        
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return

    if data == "kbb_menu":
        if chat_type != "private":
            await query.answer("✂️ Vào chat riêng với Bot để chơi!", show_alert=True)
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
        
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return


    if data.startswith("buy_salary_"):
        # Lấy số tiền muốn đổi từ data (buy_salary_1000)
        vnd_amount = int(data.split("_")[-1]) 
        cost_xu = vnd_amount * 100 # Tỷ lệ 100 Xu = 1 VND -> 1000 VND = 100.000 Xu
        
        db = SessionLocal()
        emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
        
        if not emp: db.close(); return

        if emp.coin >= cost_xu:
            # 1. Trừ Xu, Cộng Lương
            emp.coin -= cost_xu
            emp.balance += vnd_amount
            
            # 2. Ghi lịch sử ShopLog
            log = ShopLog(
                staff_id=str(user.id),
                item_name=f"Quy đổi {vnd_amount}đ Lương",
                cost=cost_xu,
                status="done"
            )
            db.add(log)
            db.commit()
            
            # 3. Thông báo thành công
            msg = (
                f"✅ <b>GIAO DỊCH THÀNH CÔNG!</b>\n"
                f"➖ Trừ: {cost_xu:,.0f} Xu\n"
                f"➕ Cộng: {vnd_amount:,.0f}đ vào Lương\n"
                f"💰 Ví hiện tại: {emp.balance:,.0f}đ\n"
                f"🪙 Xu còn lại: {emp.coin:,.0f} Xu"
            )
            await query.edit_message_text(msg, parse_mode="HTML")
        else:
            # Báo lỗi không đủ tiền
            await query.answer(f"❌ Nghèo quá! Cần {cost_xu:,.0f} Xu mới mua được.", show_alert=True)
            
        db.close()
        return

    # --- NHÓM 2: TÀI XỈU ---
    if data.startswith("tx_chon_"):
        choice = "XỈU" if "xiu" in data else "TÀI"
        code = "xiu" if "xiu" in data else "tai"
        txt = f"Bạn chọn: <b>{choice}</b>\n🪙 Cược bao nhiêu Xu:"
        
        # Mức cược: 10k, 20k, 50k, 100k Xu
        kb = [
            [
                InlineKeyboardButton("10k", callback_data=f"tx_play_{code}_10000"), 
                InlineKeyboardButton("20k", callback_data=f"tx_play_{code}_20000"), 
                InlineKeyboardButton("50k", callback_data=f"tx_play_{code}_50000"), 
                InlineKeyboardButton("100k", callback_data=f"tx_play_{code}_100000")
            ], 
            [InlineKeyboardButton("🔙 Chọn lại", callback_data="menu_tx")]
        ]
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return

    if data.startswith("tx_play_"):
        try:
            try: await query.message.delete()
            except: pass

            parts = data.split("_")
            choice_code = parts[2]
            amount = int(parts[3]) # Đây là số Xu
            
            db = SessionLocal()
            emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
            
            # Đổi kiểm tra balance -> coin
            if not emp or emp.coin < amount: 
                await context.bot.send_message(user.id, "💸 Nghèo quá! Không đủ Xu để chơi.")
                db.close(); return

            # Trừ Xu
            emp.coin -= amount
            db.commit()

            # Tung xúc xắc (Giữ nguyên)
            msg_wait = await context.bot.send_message(chat_id=query.message.chat_id, text=f"🎲 Đang tung ({amount:,.0f} Xu)...")
            m1 = await context.bot.send_dice(chat_id=query.message.chat_id)
            m2 = await context.bot.send_dice(chat_id=query.message.chat_id)
            m3 = await context.bot.send_dice(chat_id=query.message.chat_id)
            
            d1, d2, d3 = m1.dice.value, m2.dice.value, m3.dice.value
            total = d1 + d2 + d3
            result_str = "XỈU" if total <= 10 else "TÀI"

            await asyncio.sleep(3.5)
            
            # Tính toán kết quả
            is_win = False
            if d1 == d2 == d3: 
                note = f"⛈️ <b>BÃO {d1}! (Thua sạch)</b>"
            elif (choice_code == "xiu" and total <= 10) or (choice_code == "tai" and total > 10):
                profit = int(amount * 0.85) # Ăn 0.85
                emp.coin += (amount + profit) # Cộng lại Xu
                note = f"✅ <b>THẮNG!</b> (+{profit:,.0f} Xu)"
            else: 
                note = f"❌ <b>THUA!</b> (-{amount:,.0f} Xu)"
            
            db.commit()

            # Gửi kết quả (Hiển thị Xu)
            final_msg = f"📊 Kết quả: [{d1}] [{d2}] [{d3}] = <b>{total}</b> ({result_str})\n{note}\n🪙 Xu hiện có: {emp.coin:,.0f}"
            kb = [[InlineKeyboardButton("🔄 Chơi tiếp", callback_data="menu_tx")]]
            await context.bot.send_message(chat_id=query.message.chat_id, text=final_msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

            for m in [msg_wait, m1, m2, m3]:
                try: await m.delete()
                except: pass

        except Exception as e: print(e)
        finally: db.close()
        return

    # --- LOGIC TẠO KÈO (Người chơi bấm ở Chat Riêng -> Bot gửi vào Nhóm) ---
    # --- TÌM VÀ THAY THẾ ĐOẠN pk_create_ BẰNG ĐOẠN NÀY ---
    if data.startswith("pk_create_"):
        amount = int(data.split("_")[-1])
        db = SessionLocal()
        emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
        
        # Kiểm tra Xu
        if not emp or emp.coin < amount: 
            await query.answer("💸 Không đủ Xu!", show_alert=True)
            db.close(); return
            
        await query.edit_message_text(f"✅ Đã gửi lời thách đấu <b>{amount:,.0f} Xu</b> vào nhóm!", parse_mode="HTML")

        # Nội dung tin nhắn (Caption)
        kb = [[InlineKeyboardButton("🥊 NHẬN KÈO NGAY", callback_data="pk_join")]]
        msg_content = (
            f"🔥 <b>PK THÁCH ĐẤU (XU)</b> 🔥\n"
            f"👤 <b>{emp.name}</b> đang tìm đối thủ!\n"
            f"🪙 Cược: <b>{amount:,.0f} Xu</b>\n"
            f"👇 <i>Ai dám nhận không?</i>"
        )

        try:
            # --- SỬA ĐOẠN NÀY: DÙNG send_photo THAY VÌ send_message ---
            # Mở file ảnh từ thư mục static (Nhớ đảm bảo tên file đúng y chang)
            photo_file = open("static/pk_invite.jpg", "rb")
            
            sent_msg = await context.bot.send_photo(
                chat_id=MAIN_GROUP_ID,
                message_thread_id=GAME_TOPIC_ID,
                photo=photo_file,       # File ảnh
                caption=msg_content,    # Nội dung chữ
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode="HTML"
            )
            # -----------------------------------------------------------

            ACTIVE_PK_MATCHES[sent_msg.message_id] = {
                "creator_id": str(user.id), 
                "creator_name": emp.name, 
                "amount": amount
            }
        except Exception as e:
            # Nếu lỗi (ví dụ quên up ảnh), bot sẽ báo về cho người tạo
            await context.bot.send_message(user.id, f"⚠️ Lỗi: Có thể chưa thêm Bot vào nhóm hoặc thiếu file ảnh!\n({e})")

        db.close(); return
        
    # --- SỬA ĐOẠN 5: NHẬN KÈO PK VÀ CHẠY GAME ---
    if data == "pk_join":
        invite_msg_id = query.message.message_id
        group_chat_id = query.message.chat_id
        
        match_info = ACTIVE_PK_MATCHES.get(invite_msg_id)
        if not match_info: await query.answer("❌ Kèo đã hủy hoặc có người nhận rồi!", show_alert=True); return
            
        challenger_id = str(user.id)
        creator_id = match_info["creator_id"]
        amount = match_info["amount"] # Số Xu cược
        
        if challenger_id == creator_id: await query.answer("🚫 Đừng tự chơi với mình!", show_alert=True); return
            
        db = SessionLocal()
        p1 = db.query(Employee).filter(Employee.telegram_id == creator_id).first() # Chủ kèo
        p2 = db.query(Employee).filter(Employee.telegram_id == challenger_id).first() # Người nhận
        
        # Kiểm tra Xu của cả 2
        if not p2 or p2.coin < amount: await query.answer("💸 Bạn không đủ Xu!", show_alert=True); db.close(); return
        if p1.coin < amount: await query.answer("❌ Chủ kèo đã hết Xu!", show_alert=True); db.close(); return

        # Trừ Xu
        p1.coin -= amount
        p2.coin -= amount
        db.commit()

        if invite_msg_id in ACTIVE_PK_MATCHES: del ACTIVE_PK_MATCHES[invite_msg_id]

        # 1. Bắt đầu tung xúc xắc
        start_msg = await context.bot.send_message(group_chat_id, f"🥊 <b>TRẬN ĐẤU BẮT ĐẦU!</b>\n🔴 {match_info['creator_name']} VS 🔵 {p2.name}", parse_mode="HTML")
        
        m1 = await context.bot.send_dice(group_chat_id)
        d1 = m1.dice.value
        await asyncio.sleep(2)
        
        m2 = await context.bot.send_dice(group_chat_id)
        d2 = m2.dice.value
        await asyncio.sleep(3.5)

        # 2. Tính kết quả (Cộng Xu)
        total_pot = amount * 2
        fee = int(total_pot * 0.05) # Phí sàn 5%
        prize = total_pot - fee
        
        result_txt = f"🥊 <b>KẾT QUẢ PK</b> ({amount:,.0f} Xu)\n"
        
        if d1 > d2: 
            p1.coin += prize
            result_txt += f"🔴 {match_info['creator_name']}: {d1} 🏆 <b>THẮNG</b>\n🔵 {p2.name}: {d2}\n🪙 +{prize:,.0f} Xu"
            winner_balance = p1.coin
            loser_balance = p2.coin
        elif d2 > d1: 
            p2.coin += prize
            result_txt += f"🔴 {match_info['creator_name']}: {d1}\n🔵 {p2.name}: {d2} 🏆 <b>THẮNG</b>\n🪙 +{prize:,.0f} Xu"
            winner_balance = p2.coin
            loser_balance = p1.coin
        else: 
            p1.coin += amount; p2.coin += amount
            result_txt += f"🔴 {match_info['creator_name']}: {d1}\n🔵 {p2.name}: {d2}\n🤝 <b>HÒA!</b> Hoàn Xu."
            winner_balance = p1.coin # Hòa thì lấy số dư hiện tại
            loser_balance = p2.coin

        db.commit()
        
        # 3. Hiện kết quả tại nhóm
        result_msg = await context.bot.send_message(group_chat_id, result_txt, parse_mode="HTML")
        
        # 4. Gửi kết quả RIÊNG TƯ về bot (Để lưu bằng chứng & Số dư)
        private_log = f"{result_txt}\n➖➖➖➖➖➖\n🪙 Xu hiện tại: "
        try: await context.bot.send_message(creator_id, private_log + f"{p1.coin:,.0f}", parse_mode="HTML")
        except: pass
        
        try: await context.bot.send_message(challenger_id, private_log + f"{p2.coin:,.0f}", parse_mode="HTML")
        except: pass

        # 5. Đợi 10 giây rồi XÓA SẠCH ở nhóm (Theo đúng yêu cầu)
        await asyncio.sleep(10)
        messages_to_delete = [invite_msg_id, start_msg.message_id, m1.message_id, m2.message_id, result_msg.message_id]
        
        for mid in messages_to_delete:
            try: await context.bot.delete_message(chat_id=group_chat_id, message_id=mid)
            except: pass
            
        db.close()
        return
        
# --- HÀM PHỤ: CHỐNG SPAM & MUTE TỰ ĐỘNG ---
async def check_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. Nếu là chat riêng thì cho qua
    if update.effective_chat.type == "private":
        return True
    
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # 2. Xóa tin nhắn lệnh ngay lập tức
    try: await update.message.delete()
    except: pass
    
    # --- LOGIC CHỐNG SPAM ---
    user_id = user.id
    now = time.time()
    
    # Tạo hồ sơ nếu chưa có
    if user_id not in SPAM_TRACKER:
        SPAM_TRACKER[user_id] = []
        
    # Lọc bỏ các lần spam cũ quá 10 giây trước
    SPAM_TRACKER[user_id] = [t for t in SPAM_TRACKER[user_id] if now - t < 10]
    
    # Ghi nhận lần spam này
    SPAM_TRACKER[user_id].append(now)
    
    # Nếu spam quá 3 lần trong 10 giây -> MUTE 5 PHÚT
    if len(SPAM_TRACKER[user_id]) >= 3:
        try:
            # Mute 5 phút (300 giây)
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=now + 300 
            )
            
            # Thông báo trừng phạt
            msg = await context.bot.send_message(chat_id, f"🚫 <b>{user.first_name}</b> spam quá nhiều! Bị cấm chat 5 phút.", parse_mode="HTML")
            
            # Reset bộ đếm để tránh mute chồng
            SPAM_TRACKER[user_id] = []
            
            # Xóa thông báo sau 10s
            await asyncio.sleep(10)
            try: 
                await msg.delete()
            except: 
                pass
            
        except Exception as e:
            # Nếu Bot không có quyền Admin thì chỉ cảnh báo
            msg = await context.bot.send_message(chat_id, f"⚠️ Đừng spam nữa {user.first_name}!")
            await asyncio.sleep(3)
            
            # --- ĐOẠN ĐÃ SỬA LỖI ---
            try: 
                await msg.delete()
            except: 
                pass
            # -----------------------
            
        return False

    # Nếu chưa đến mức bị Mute thì chỉ nhắc nhở nhẹ
    if len(SPAM_TRACKER[user_id]) == 1:
        msg = await update.message.reply_text(f"🤫 {user.first_name}, qua nhắn riêng với Bot nhé!")
        await asyncio.sleep(5)
        try: 
            await msg.delete()
        except: 
            pass
    
    return False
# --- CÁC LỆNH BOT ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_private(update, context): return
    user = update.effective_user
    db = SessionLocal()
    emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
    
    if not emp:
        # Logic tạo nhân viên mới
        used_emojis = [e.emoji for e in db.query(Employee).all()]
        available = [e for e in EMOJI_POOL if e not in used_emojis]
        if not available:
            await update.message.reply_text("Hết icon! Liên hệ Admin.")
            db.close(); return
        emoji = random.choice(available)
        emp = Employee(telegram_id=str(user.id), name=user.full_name, emoji=emoji)
        db.add(emp)
        db.commit()
    
    link = f"{WEB_URL}/?ref={user.id}"
    qr_api = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={link}"
    msg = (
        f"Chào <b>{emp.name}</b> {emp.emoji}!\n"
        f"Chúc một ngày làm việc năng suất.\n"
        f"👇 <i>Chọn menu bên dưới:</i>"
    )
    # Gửi tin nhắn kèm MENU NÚT BẤM
    await update.message.reply_text(msg, reply_markup=get_main_menu(), parse_mode="HTML")
    db.close()
    
# --- HÀM GỌI MENU ORDER TRONG NHÓM ---
async def order_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Nút bấm Inline mở Web App
    kb = [
        [InlineKeyboardButton("⚡ MỞ MENU ORDER ⚡", web_app=WebAppInfo(url=f"{WEB_URL}/webapp"))]
    ]
    # Gửi vào nhóm
    await update.message.reply_text(
        "👇 Bấm vào nút bên dưới để lên đơn nhé:", 
        reply_markup=InlineKeyboardMarkup(kb)
    )


async def me_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_private(update, context): return
    user = update.effective_user
    db = SessionLocal()
    emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
    
    if emp:
        wait_msg = await update.message.reply_text("📸 Đợi cái ní, đang lấy avt để in thẻ...")
        
        # Lấy Avatar (Giữ nguyên)
        avatar_io = None
        try:
            photos = await user.get_profile_photos(limit=1)
            if photos.total_count > 0:
                photo_file = await photos.photos[0][-1].get_file()
                avatar_bytes = await photo_file.download_as_bytearray()
                avatar_io = io.BytesIO(avatar_bytes)
        except: pass

        # --- SỬA DÒNG NÀY: Truyền thêm emp.coin vào hàm ---
        loop = asyncio.get_running_loop()
        photo_file = await loop.run_in_executor(None, create_card_image, emp.name, emp.emoji, emp.balance, emp.coin, avatar_io)

        rank_name, rank_icon = get_rank_info(emp.balance) # Rank vẫn tính bằng balance

        # Sửa caption hiển thị cả 2 loại tiền
        caption = (
            f"💳 <b>THẺ NHÂN VIÊN</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👤 <b>Cấp bậc:</b> {rank_icon} {rank_name}\n"
            f"💰 <b>Lương:</b> {emp.balance:,.0f}đ\n"
            f"🪙 <b>Xu game:</b> {emp.coin:,.0f} xu\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👉 <i>Gõ /diemdanh để nhận Xu mỗi ngày!</i>"
        )

        await update.message.reply_photo(photo=photo_file, caption=caption, parse_mode="HTML")
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=wait_msg.message_id)
        
    else:
        await update.message.reply_text("Chưa đăng ký. Bấm /start")
    
    db.close()
    
async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_private(update, context): return
    db = SessionLocal()
    
    # Top 5 Đại Gia (Lương)
    top_balance = db.query(Employee).order_by(desc(Employee.balance)).limit(5).all()
    
    # Top 5 Con Bạc (Xu) - MỚI
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

async def qr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_private(update, context): return
    user_id = str(update.effective_user.id)
    link = f"{WEB_URL}/?ref={user_id}"
    qr_api = f"https://api.qrserver.com/v1/create-qr-code/?size=500x500&data={link}"
    await update.message.reply_photo(photo=qr_api, caption="🚀 <b>Mã QR Tốc Độ Cao</b>\nĐưa khách quét ngay!", parse_mode="HTML")

# --- LOGIC ĐIỂM DANH (NHẬN 10K XU) ---
async def daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Điểm danh hàng ngày với streak bonus"""
    user = update.effective_user
    
    db = SessionLocal()
    emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
    
    if not emp:
        await update.message.reply_text("❌ Bạn chưa được đăng ký trong hệ thống!")
        db.close()
        return
    
    today = date.today()
    
    # Kiểm tra đã điểm danh hôm nay chưa
    if emp.last_checkin == today:
        await update.message.reply_text(
            f"⚠️ Bạn đã điểm danh hôm nay rồi!\n"
            f"🔥 Streak hiện tại: {emp.checkin_streak} ngày\n"
            f"📅 Quay lại vào ngày mai nhé!"
        )
        db.close()
        return
    
    # Tính streak
    yesterday = today - timedelta(days=1)
    
    if emp.last_checkin == yesterday:
        # Điểm danh liên tục
        emp.checkin_streak += 1
    else:
        # Reset streak (quên điểm danh)
        emp.checkin_streak = 1
    
    # Thưởng cơ bản
    base_reward = 10000
    bonus = 0
    bonus_text = ""
    
    # Bonus streak 7 ngày
    if emp.checkin_streak >= 7 and emp.checkin_streak % 7 == 0:
        bonus = 30000
        bonus_text = f"\n🎁 <b>BONUS 7 NGÀY: +{bonus:,.0f} Xu!</b>"
    
    total_reward = base_reward + bonus
    emp.coin += total_reward
    emp.last_checkin = today
    
    db.commit()
    
    # Hiển thị streak progress
    streak_display = ""
    for i in range(1, 8):
        if i <= (emp.checkin_streak % 7) or (emp.checkin_streak % 7 == 0 and emp.checkin_streak > 0):
            streak_display += "🟢"
        else:
            streak_display += "⚪"
    
    msg = (
        f"📅 <b>ĐIỂM DANH THÀNH CÔNG!</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💰 +{base_reward:,.0f} Xu{bonus_text}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🔥 Streak: <b>{emp.checkin_streak} ngày</b>\n"
        f"📊 Tuần này: {streak_display}\n"
        f"🪙 Xu hiện có: <b>{emp.coin:,.0f}</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💡 Điểm danh 7 ngày liên tục = +30,000 Xu!"
    )
    
    await update.message.reply_text(msg, parse_mode="HTML")
    db.close()

GIFT_REWARDS = [
    (5000, 50),   # 5000 Xu - 50%
    (10000, 30),  # 10000 Xu - 30%
    (15000, 15),  # 15000 Xu - 15%
    (20000, 5),   # 20000 Xu - 5%
]

def get_random_gift():
    """Random phần thưởng theo tỉ lệ"""
    total = sum(weight for _, weight in GIFT_REWARDS)
    r = random.randint(1, total)
    cumulative = 0
    for reward, weight in GIFT_REWARDS:
        cumulative += weight
        if r <= cumulative:
            return reward
    return GIFT_REWARDS[0][0]


async def gift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mở hộp quà may mắn - FREE 1 lần/ngày"""
    user = update.effective_user
    
    db = SessionLocal()
    emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
    
    if not emp:
        await update.message.reply_text("❌ Bạn chưa được đăng ký trong hệ thống!")
        db.close()
        return
    
    today = date.today()
    
    # Kiểm tra đã mở quà hôm nay chưa
    if emp.last_gift_open == today:
        await update.message.reply_text(
            f"🎁 Bạn đã mở quà hôm nay rồi!\n"
            f"📅 Quay lại vào ngày mai nhé!"
        )
        db.close()
        return
    
    # Random phần thưởng
    reward = get_random_gift()
    
    # Cập nhật
    emp.coin += reward
    emp.last_gift_open = today
    db.commit()
    
    # Hiệu ứng mở hộp
    if reward == 20000:
        effect = "🎉🎊🎉 SIÊU HIẾM! 🎉🎊🎉"
        emoji = "💎"
    elif reward == 15000:
        effect = "✨ HIẾM! ✨"
        emoji = "🌟"
    elif reward == 10000:
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
# 4. THÔNG BÁO TỰ ĐỘNG 8H & 17H
# ==========================================

MORNING_MESSAGES = [
    "☀️ <b>CHÀO BUỔI SÁNG CA SÁNG!</b>\n\nChúc toàn thể nhân sự ca sáng bắt đầu ngày mới với sự tập trung và năng lượng cao nhất. Hãy chuẩn bị mọi thứ thật chỉn chu.\n\n❤️ Thả tim để nhận 1,000 Xu!",

    "🌅 <b>KHỞI ĐẦU NGÀY MỚI TẠI KHỈ MILKTEA.</b>\n\nChúc team ca sáng làm việc hiệu quả, phối hợp nhịp nhàng để mang lại trải nghiệm tốt nhất cho khách hàng.\n\n❤️ Thả tim để nhận 1,000 Xu!",

    "🌞 <b>THÔNG BÁO CA SÁNG.</b>\n\nChúc các bạn một ca làm việc thuận lợi. Hãy duy trì tiêu chuẩn chất lượng và vệ sinh cửa hàng lên hàng đầu.\n\n❤️ Thả tim để nhận 1,000 Xu!",

    "⚡ <b>TINH THẦN KHỈ MILKTEA.</b>\n\nNghiêm túc trong công việc và nhiệt huyết trong phục vụ. Chúc team ca sáng hoàn thành tốt nhiệm vụ được giao.\n\n❤️ Thả tim để nhận 1,000 Xu!",

    "🍃 <b>CHÀO NGÀY MỚI NĂNG ĐỘNG.</b>\n\nMọi sự chuẩn bị tốt vào buổi sáng sẽ mang lại kết quả tốt cho cả ngày. Cố lên nhé team ca sáng!\n\n❤️ Thả tim để nhận 1,000 Xu!",

    "📋 <b>TRIỂN KHAI CÔNG VIỆC CA SÁNG.</b>\n\nChúc cả team một ngày làm việc chuyên nghiệp, xử lý đơn hàng nhanh chóng và chính xác.\n\n❤️ Thả tim để nhận 1,000 Xu!",

    "💎 <b>CAM KẾT CHẤT LƯỢNG.</b>\n\nBắt đầu ngày mới bằng sự tận tâm. Chúc các chiến binh Khỉ Milktea ca sáng gặt hái được nhiều thành công.\n\n❤️ Thả tim để nhận 1,000 Xu!"
]
EVENING_MESSAGES = [
    "🌇 <b>BẮT ĐẦU CA CHIỀU.</b>\n\nChúc toàn đội ngũ ca chiều giữ vững phong độ, làm việc tập trung để hoàn thành chỉ tiêu trong ngày.\n\n❤️ Thả tim để nhận 1,000 Xu!",

    "🌆 <b>CHÀO TEAM CA CHIỀU.</b>\n\nDù cuối ngày có thể mệt mỏi, hãy cùng nhau duy trì sự chuyên nghiệp đến những đơn hàng cuối cùng.\n\n❤️ Thả tim để nhận 1,000 Xu!",

    "🚀 <b>TẬP TRUNG CA CAO ĐIỂM.</b>\n\nCa chiều là thời điểm quan trọng, chúc team phối hợp ăn ý và xử lý công việc thật hiệu quả.\n\n❤️ Thả tim để nhận 1,000 Xu!",

    "🤝 <b>TINH THẦN ĐỒNG ĐỘI.</b>\n\nCảm ơn nỗ lực của các bạn trong ca chiều. Hãy hỗ trợ nhau để đảm bảo vận hành tốt nhất tại Khỉ Milktea.\n\n❤️ Thả tim để nhận 1,000 Xu!",

    "🌙 <b>NỖ LỰC VỀ ĐÍCH.</b>\n\nChúc team ca chiều có một buổi làm việc năng suất. Sự tỉ mỉ của các bạn chính là bộ mặt của thương hiệu.\n\n❤️ Thả tim để nhận 1,000 Xu!",

    "🎯 <b>MỤC TIÊU CA CHIỀU.</b>\n\nHãy đảm bảo mọi quy trình được thực hiện chuẩn xác. Chúc cả team có một ca làm việc thuận lợi và an lành.\n\n❤️ Thả tim để nhận 1,000 Xu!",

    "✨ <b>HOÀN THÀNH NHIỆM VỤ.</b>\n\nChúc các bạn ca chiều làm việc đầy nhiệt huyết, giữ vững uy tín chất lượng của Khỉ Milktea cho đến khi đóng cửa.\n\n❤️ Thả tim để nhận 1,000 Xu!"
]


async def send_daily_announcement(context: ContextTypes.DEFAULT_TYPE, is_morning: bool):
    """Gửi thông báo tự động"""
    global DAILY_ANNOUNCEMENT_MSG
    
    messages = MORNING_MESSAGES if is_morning else EVENING_MESSAGES
    text = random.choice(messages)
    
    try:
        sent_msg = await context.bot.send_message(
            chat_id=MAIN_GROUP_ID,
            message_thread_id=CHAT_TOPIC_ID,
            text=text,
            parse_mode="HTML"
        )
        
        # Lưu message_id để track react
        DAILY_ANNOUNCEMENT_MSG[sent_msg.message_id] = set()
        
        # Tự động xóa khỏi dict sau 24h để tránh memory leak
        async def cleanup():
            await asyncio.sleep(86400)  # 24 giờ
            DAILY_ANNOUNCEMENT_MSG.pop(sent_msg.message_id, None)
        
        asyncio.create_task(cleanup())
        
    except Exception as e:
        print(f"Lỗi gửi thông báo: {e}")


async def schedule_announcements(context: ContextTypes.DEFAULT_TYPE):
    """Lên lịch gửi thông báo 8h và 17h"""
    import pytz
    
    vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    
    while True:
        now = datetime.now(vn_tz)
        
        # Tính thời gian đến 8h sáng
        next_8am = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if now.hour >= 8:
            next_8am += timedelta(days=1)
        
        # Tính thời gian đến 17h chiều
        next_5pm = now.replace(hour=17, minute=0, second=0, microsecond=0)
        if now.hour >= 17:
            next_5pm += timedelta(days=1)
        
        # Chọn thời điểm gần nhất
        if next_8am < next_5pm:
            wait_seconds = (next_8am - now).total_seconds()
            is_morning = True
        else:
            wait_seconds = (next_5pm - now).total_seconds()
            is_morning = False
        
        # Chờ đến giờ
        await asyncio.sleep(wait_seconds)
        
        # Gửi thông báo
        await send_daily_announcement(context, is_morning)
        
        # Chờ 1 phút tránh gửi trùng
        await asyncio.sleep(60)


# ==========================================
# 5. XỬ LÝ REACTION TẶNG XU
# ==========================================

async def handle_reaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi có người react tin nhắn"""
    global DAILY_ANNOUNCEMENT_MSG
    
    reaction = update.message_reaction
    if not reaction:
        return
    
    message_id = reaction.message_id
    user_id = reaction.user.id if reaction.user else None
    
    if not user_id:
        return
    
    # Kiểm tra có phải tin nhắn thông báo không
    if message_id not in DAILY_ANNOUNCEMENT_MSG:
        return
    
    # Kiểm tra đã react chưa
    if user_id in DAILY_ANNOUNCEMENT_MSG[message_id]:
        return
    
    # Kiểm tra có react ❤️ không
    new_reactions = reaction.new_reaction
    has_heart = any(
        r.emoji == "❤" or r.emoji == "❤️" 
        for r in new_reactions
    ) if new_reactions else False
    
    if not has_heart:
        return
    
    # Cộng Xu
    db = SessionLocal()
    emp = db.query(Employee).filter(Employee.telegram_id == str(user_id)).first()
    
    if emp:
        emp.coin += 1000
        db.commit()
        
        # Đánh dấu đã react
        DAILY_ANNOUNCEMENT_MSG[message_id].add(user_id)
        
        # Thông báo riêng
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"❤️ Cảm ơn bạn đã tương tác!\n💰 +1,000 Xu\n🪙 Xu hiện có: {emp.coin:,.0f}"
            )
        except:
            pass
    
    db.close()


# --- LOGIC HIỂN THỊ MENU SHOP ---
async def shop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_private(update, context): return
    user = update.effective_user
    db = SessionLocal()
    emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
    
    if not emp: db.close(); return

    msg = (
        f"🛒 <b>TẠP HÓA CỦA KHỈ</b> 🛒\n"
        f"👤 Khách: <b>{emp.name}</b>\n"
        f"hw <b>{emp.coin:,.0f} Xu</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👇 <i>Chọn món muốn mua:</i>"
    )
    
    # Nút bấm mua hàng
    keyboard = [
        [
            # Nút đổi tiền: Callback data chứa loại và giá
            InlineKeyboardButton("💸 1k Lương (100k Xu)", callback_data="buy_salary_1000")
        ],
        [InlineKeyboardButton("❌ Đóng Shop", callback_data="close_menu")]
    ]
    
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    db.close()

# --- ADMIN SYSTEM ---
async def handle_add_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text: return
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    db = SessionLocal()
    count = 0
    try:
        for content in lines:
            db.add(Review(content=content))
            count += 1
        db.commit()
        await update.message.reply_text(f"✅ Đã thêm {count} câu review.")
    except: pass
    db.close()

async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID: return
    keyboard = [
        ["📋 Danh Sách NV", "📢 Gửi Thông Báo"],
        ["📝 Xem Kho Review", "🗑 Xóa Hết Review"],
        ["🔄 Reset Toàn Bộ", "❌ Thoát Admin"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("🔓 <b>MENU ADMIN</b>", reply_markup=reply_markup, parse_mode="HTML")

async def handle_admin_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_private(update, context): return

    text = update.message.text
    user_id = str(update.effective_user.id)

    # Các nút Menu Nhân Viên
    if text == "💳 Ví & Thẻ":
        await me_command(update, context)
        return
    elif text == "📅 Điểm Danh":
        await daily_command(update, context)
        return
    elif text == "🛒 Shop Xu":
        await shop_command(update, context)
        return
    elif text == "🎰 Giải Trí":
        await game_ui_command(update, context)
        return
    elif text == "🏆 BXH Đại Gia": # Thêm xử lý nút BXH
        await top_command(update, context)
        return
    elif text == "🚀 Lấy mã QR": # Thêm xử lý nút QR
        await qr_command(update, context)
        return

    # --- XỬ LÝ MENU ADMIN (Chỉ Admin mới dùng được) ---
    if user_id == ADMIN_ID:
        admin_buttons = ["📋 Danh Sách NV", "📢 Gửi Thông Báo", "🔄 Reset Toàn Bộ", "❌ Thoát Admin", "📝 Xem Kho Review", "🗑 Xóa Hết Review"]
    if text not in admin_buttons:
        await handle_add_review(update, context)
        return

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
                    f"👉 Xu:      /tipxu_{e.telegram_id} | /finex_{e.telegram_id}\n"
                    f"🗑 Xóa:    /del_{e.telegram_id}\n"
                )
        if len(msg) > 4000: 
            msg = msg[:4000] + "\n...(Danh sách quá dài, bị cắt bớt)"
            
        await update.message.reply_text(msg, parse_mode="HTML")
    elif text == "📝 Xem Kho Review":
        reviews = db.query(Review).all()
        msg = "📝 <b>REVIEW:</b>\n" + "\n".join([f"- {r.content}" for r in reviews]) if reviews else "Trống."
        if len(msg)>4000: msg=msg[:4000]+"..."
        await update.message.reply_text(msg)
    elif text == "🗑 Xóa Hết Review":
        db.query(Review).delete(); db.commit(); await update.message.reply_text("🗑 Đã xóa sạch.")
    elif text == "🔄 Reset Toàn Bộ":
        db.query(Employee).update({Employee.balance: 0}); db.commit(); await update.message.reply_text("✅ Đã reset ví.")
    elif text == "📢 Gửi Thông Báo":
        await update.message.reply_text("⚠️ Gõ: `/thong_bao Nội dung`", parse_mode="Markdown")
    elif text == "❌ Thoát Admin":
        await update.message.reply_text("🔒 Đã thoát.", reply_markup=ReplyKeyboardRemove())
    db.close()

async def quick_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID: return
    command = update.message.text 
    try:
        action_part, target_id = command[1:].split('_')
    except: return
        
    db = SessionLocal()
    emp = db.query(Employee).filter(Employee.telegram_id == target_id).first()
    if emp:
        # Xử lý Tiền thật
        if action_part == "tip": 
            emp.balance += 5000
            await update.message.reply_text(f"✅ Thưởng nóng 5k lương cho {emp.name}.")
        elif action_part == "fine": 
            emp.balance -= 5000
            await update.message.reply_text(f"🚫 Phạt 5k lương của {emp.name}.")
            
        # Xử lý Xu (MỚI) - Thưởng/Phạt 50k Xu một lần
        elif action_part == "tipxu": 
            emp.coin += 50000
            await update.message.reply_text(f"✅ Buff 50k Xu cho {emp.name}.")
        elif action_part == "finex": 
            emp.coin -= 50000
            await update.message.reply_text(f"🚫 Tịch thu 50k Xu của {emp.name}.")
            
        db.commit()
    db.close()

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID: return
    msg = " ".join(context.args)
    if msg:
        db = SessionLocal(); emps = db.query(Employee).all()
        for e in emps: 
            try: await context.bot.send_message(e.telegram_id, f"📢 <b>THÔNG BÁO:</b>\n{msg}", parse_mode="HTML")
            except: pass
        await update.message.reply_text(f"✅ Đã gửi.")
        db.close()

import json # Thêm vào đầu file main.py

# --- HÀM XỬ LÝ DỮ LIỆU TỪ WEBAPP ---
async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = json.loads(update.effective_message.web_app_data.data)
        user = update.effective_user
        
        customer = data.get("customer", "Khách")
        items = data.get("items")
        total = data.get("total")

        # ĐỊNH DẠNG SIÊU GỌN CHO THU NGÂN
        # Cấu trúc: [Tên khách] - [Tên phục vụ]
        # Món x Số lượng (Topping)
        msg = f"🔔 <b>ĐƠN:</b> {customer.upper()} ({user.first_name})\n"
        
        for item in items:
            # Gom topping và ghi chú vào ngoặc đơn
            extra = []
            if item.get('tops'):
                extra.extend([t['name'] for t in item['tops']])
            if item.get('notes'):
                extra.extend(item['notes'])
            
            detail = f" ({', '.join(extra)})" if extra else ""
            msg += f"• {item['qty']}x <b>{item['name']}</b>{detail}\n"
        

        # Nút bấm để thu ngân xác nhận đã nhập máy
        kb = [[InlineKeyboardButton("✅ ĐÃ NHẬP MÁY", callback_data="pos_done")]]
        
        await context.bot.send_message(
            chat_id=MAIN_GROUP_ID, 
            text=msg, 
            message_thread_id=ORDER_TOPIC_ID,
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Lỗi WebApp Data: {e}")

# --- LỆNH ĐĂNG KÝ NHÂN VIÊN ---
async def dangky_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_private(update, context): return
    user = update.effective_user
    text = update.message.text.strip()
    
    # Hướng dẫn nếu thiếu tham số
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
    
    # Validate SĐT
    if not phone.isdigit() or len(phone) < 9:
        await update.message.reply_text("❌ SĐT không hợp lệ! Vui lòng nhập số điện thoại đúng.")
        return
    
    # Đăng ký
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


# --- LỆNH XEM DANH SÁCH NHÂN VIÊN (ADMIN) ---
async def dsnv_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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


# --- LỆNH XÓA NHÂN VIÊN (ADMIN) ---
async def xoanv_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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


# --- CALLBACK HỦY ĐƠN VÀ ĐÃ NHẬP MÁY ---
async def order_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    # Xử lý nút HỦY ĐƠN
    if data.startswith("cancel_order_"):
        allowed_user_id = int(data.replace("cancel_order_", ""))
        
        # Kiểm tra người bấm
        if user_id != allowed_user_id:
            # Im lặng, không phản hồi
            await query.answer()
            return
        
        # Đúng người → Xóa tin nhắn
        try:
            await query.message.delete()
            await query.answer("✅ Đã hủy đơn!")
        except Exception as e:
            await query.answer(f"Lỗi: {e}", show_alert=True)
        return
    
    # Xử lý nút ĐÃ NHẬP MÁY (giữ nguyên logic cũ nhưng xóa nút Hủy)
    if data == "pos_done":
        original_text = query.message.text_html if query.message.text_html else query.message.text
        new_text = f"{original_text}\n\n✅ <b>Đã nhập máy</b>"
        
        try:
            await query.message.edit_text(text=new_text, parse_mode="HTML", reply_markup=None)
            await query.answer("✅ Đã xác nhận!")
        except:
            await query.answer("Đã xử lý!")
        return
SLOT_EMOJIS = ["🍒", "🍋", "🍊", "🍇", "⭐", "💎", "7️⃣"]
SLOT_PAYOUTS = {
    "💎💎💎": 50,   # Jackpot
    "7️⃣7️⃣7️⃣": 30,
    "⭐⭐⭐": 20,
    "🍇🍇🍇": 10,
    "🍊🍊🍊": 8,
    "🍋🍋🍋": 5,
    "🍒🍒🍒": 3,
}

async def slot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị menu Slot Machine"""
    user = update.effective_user
    chat_type = update.effective_chat.type
    
    # Chỉ chơi trong chat riêng
    if chat_type != "private":
        await update.message.reply_text("🎰 Vào chat riêng với Bot để chơi Slot nhé!")
        return
    
    txt = (
        "🎰 <b>SLOT MACHINE</b> 🎰\n"
        "━━━━━━━━━━━━━━━━\n"
        "💎💎💎 = x50 (Jackpot)\n"
        "7️⃣7️⃣7️⃣ = x30\n"
        "⭐⭐⭐ = x20\n"
        "🍇🍇🍇 = x10\n"
        "🍊🍊🍊 = x8\n"
        "🍋🍋🍋 = x5\n"
        "🍒🍒🍒 = x3\n"
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
        [InlineKeyboardButton("❌ Đóng", callback_data="close_menu")]
    ]
    
    await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")


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
    
    # Trừ tiền cược
    emp.coin -= amount
    db.commit()
    
    # Xóa tin nhắn cũ
    try:
        await query.message.delete()
    except:
        pass
    
    # Gửi thông báo đang quay
    wait_msg = await context.bot.send_message(
        chat_id=user.id,
        text=f"🎰 Đang quay... (Cược: {amount:,.0f} Xu)"
    )
    
    # Gửi dice slot với animation
    dice_msg = await context.bot.send_dice(
        chat_id=user.id,
        emoji="🎰"
    )
    
    # Lấy giá trị slot (1-64)
    slot_value = dice_msg.dice.value
    
    # Chờ animation chạy xong (3 giây)
    await asyncio.sleep(3)
    
    # Tính kết quả dựa trên giá trị
    # Telegram slot: 1-64, các giá trị đặc biệt:
    # 64 = 777 (Jackpot), 43 = Bar Bar Bar, 22 = Lemon x3...
    winnings = 0
    
    if slot_value == 64:  # 777 Jackpot
        winnings = amount * 50
        note = "🎉🎉🎉 <b>JACKPOT 777!</b> x50"
    elif slot_value == 43:  # Bar x3
        winnings = amount * 20
        note = "🎊 <b>BAR BAR BAR!</b> x20"
    elif slot_value in [1, 22]:  # 3 giống nhau khác
        winnings = amount * 10
        note = "✨ <b>TRÙNG 3!</b> x10"
    elif slot_value in [2, 3, 4, 6, 11, 16, 17, 21, 32, 33, 38, 41, 42, 48, 49, 54, 59, 61, 62, 63]:
        # 2 giống nhau
        winnings = int(amount * 1.5)
        note = "👍 Trùng 2! x1.5"
    else:
        note = "😢 Không trúng!"
    
    # Cộng tiền thắng
    if winnings > 0:
        emp.coin += winnings
        db.commit()
    
    profit = winnings - amount
    profit_str = f"+{profit:,.0f}" if profit > 0 else f"{profit:,.0f}"
    
    # Xóa tin nhắn chờ
    try:
        await wait_msg.delete()
    except:
        pass
    
    # Gửi kết quả
    result_msg = (
        f"🎰 <b>KẾT QUẢ SLOT</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"{note}\n"
        f"💰 {profit_str} Xu\n"
        f"🪙 Xu hiện có: <b>{emp.coin:,.0f}</b>"
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
    
    db.close()


async def handle_slot_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quay lại menu Slot"""
    query = update.callback_query
    
    txt = (
        "🎰 <b>SLOT MACHINE</b> 🎰\n"
        "━━━━━━━━━━━━━━━━\n"
        "💎💎💎 = x50 (Jackpot)\n"
        "7️⃣7️⃣7️⃣ = x30\n"
        "⭐⭐⭐ = x20\n"
        "🍇🍇🍇 = x10\n"
        "🍊🍊🍊 = x8\n"
        "🍋🍋🍋 = x5\n"
        "🍒🍒🍒 = x3\n"
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
        [InlineKeyboardButton("❌ Đóng", callback_data="close_menu")]
    ]
    
    await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")


# ==========================================
# GAME 2: KÉO BÚA BAO (PvP)
# ==========================================

KBB_CHOICES = {
    "kbb_rock": ("✊", "Búa"),
    "kbb_paper": ("✋", "Bao"),
    "kbb_scissors": ("✌️", "Kéo")
}

KBB_RULES = {
    "kbb_rock": "kbb_scissors",     # Búa thắng Kéo
    "kbb_scissors": "kbb_paper",    # Kéo thắng Bao
    "kbb_paper": "kbb_rock"         # Bao thắng Búa
}


async def kbb_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị menu Kéo Búa Bao"""
    user = update.effective_user
    chat_type = update.effective_chat.type
    
    # Chỉ tạo kèo trong chat riêng
    if chat_type != "private":
        await update.message.reply_text("✂️ Vào chat riêng với Bot để tạo kèo Kéo Búa Bao!")
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
        [InlineKeyboardButton("❌ Đóng", callback_data="close_menu")]
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
    
    await query.edit_message_text(f"✅ Đã gửi thách đấu <b>{amount:,.0f} Xu</b> vào nhóm!", parse_mode="HTML")
    
    # Gửi vào topic Game
    msg_content = (
        f"✂️ <b>KÉO BÚA BAO</b> ✊\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"👤 <b>{emp.name}</b> thách đấu!\n"
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
        
        # Lưu thông tin trận đấu
        ACTIVE_RPS_MATCHES[sent_msg.message_id] = {
            "creator_id": str(user.id),
            "creator_name": emp.name,
            "amount": amount,
            "creator_choice": None,
            "joiner_id": None,
            "joiner_name": None,
            "joiner_choice": None
        }
    except Exception as e:
        await context.bot.send_message(user.id, f"⚠️ Lỗi: {e}")
    
    db.close()


async def handle_kbb_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Nhận kèo Kéo Búa Bao"""
    query = update.callback_query
    user = query.from_user
    msg_id = query.message.message_id
    
    match = ACTIVE_RPS_MATCHES.get(msg_id)
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
    creator = db.query(Employee).filter(Employee.telegram_id == match["creator_id"]).first()
    
    if not joiner or joiner.coin < match["amount"]:
        await query.answer("💸 Không đủ Xu!", show_alert=True)
        db.close()
        return
    
    # Cập nhật trận đấu
    match["joiner_id"] = str(user.id)
    match["joiner_name"] = joiner.name
    
    # Cập nhật tin nhắn
    txt = (
        f"✂️ <b>KÉO BÚA BAO</b> ✊\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"👤 {match['creator_name']} ⚔️ {joiner.name}\n"
        f"🪙 Cược: <b>{match['amount']:,.0f} Xu</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"⏳ Đang chờ cả 2 chọn..."
    )
    
    await query.edit_message_text(txt, parse_mode="HTML")
    
    # Gửi tin nhắn riêng cho cả 2 người chọn
    choice_kb = [
        [
            InlineKeyboardButton("✊ Búa", callback_data=f"kbb_choose_rock_{msg_id}"),
            InlineKeyboardButton("✋ Bao", callback_data=f"kbb_choose_paper_{msg_id}"),
            InlineKeyboardButton("✌️ Kéo", callback_data=f"kbb_choose_scissors_{msg_id}")
        ]
    ]
    
    choose_txt = f"✂️ <b>CHỌN VŨ KHÍ</b>\n\n⚔️ Trận với <b>{joiner.name}</b>\n🪙 Cược: {match['amount']:,.0f} Xu"
    choose_txt2 = f"✂️ <b>CHỌN VŨ KHÍ</b>\n\n⚔️ Trận với <b>{match['creator_name']}</b>\n🪙 Cược: {match['amount']:,.0f} Xu"
    
    try:
        await context.bot.send_message(
            chat_id=match["creator_id"],
            text=choose_txt,
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
        print(f"Lỗi gửi tin nhắn chọn: {e}")
    
    db.close()
    await query.answer("✅ Đã nhận kèo! Check tin nhắn riêng để chọn!")


async def handle_kbb_choose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi người chơi chọn Kéo/Búa/Bao"""
    query = update.callback_query
    user = query.from_user
    data = query.data  # kbb_choose_rock_12345
    
    parts = data.split("_")
    choice = f"kbb_{parts[2]}"  # kbb_rock, kbb_paper, kbb_scissors
    msg_id = int(parts[3])
    
    match = ACTIVE_RPS_MATCHES.get(msg_id)
    if not match:
        await query.answer("❌ Trận đấu đã kết thúc!", show_alert=True)
        return
    
    user_id = str(user.id)
    choice_emoji, choice_name = KBB_CHOICES[choice]
    
    # Lưu lựa chọn
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
    
    # Kiểm tra cả 2 đã chọn chưa
    if match["creator_choice"] and match["joiner_choice"]:
        await resolve_kbb_match(context, msg_id, match)


async def resolve_kbb_match(context: ContextTypes.DEFAULT_TYPE, msg_id: int, match: dict):
    """Xử lý kết quả trận đấu"""
    db = SessionLocal()
    
    creator = db.query(Employee).filter(Employee.telegram_id == match["creator_id"]).first()
    joiner = db.query(Employee).filter(Employee.telegram_id == match["joiner_id"]).first()
    
    c_choice = match["creator_choice"]
    j_choice = match["joiner_choice"]
    c_emoji, c_name = KBB_CHOICES[c_choice]
    j_emoji, j_name = KBB_CHOICES[j_choice]
    amount = match["amount"]
    
    # Xác định người thắng
    if c_choice == j_choice:
        result = "🤝 HÒA!"
        winner = None
    elif KBB_RULES[c_choice] == j_choice:
        result = f"🏆 <b>{match['creator_name']}</b> THẮNG!"
        winner = "creator"
    else:
        result = f"🏆 <b>{match['joiner_name']}</b> THẮNG!"
        winner = "joiner"
    
    # Xử lý tiền
    if winner == "creator":
        creator.coin += amount  # Thắng: +tiền cược của đối thủ
        joiner.coin -= amount   # Thua: -tiền cược
    elif winner == "joiner":
        joiner.coin += amount
        creator.coin -= amount
    # Hòa: không ai mất tiền
    
    db.commit()
    
    # Cập nhật tin nhắn trong group
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
    
    # Thông báo riêng cho từng người
    if winner == "creator":
        await context.bot.send_message(match["creator_id"], f"🎉 Bạn THẮNG! +{amount:,.0f} Xu\n🪙 Xu: {creator.coin:,.0f}")
        await context.bot.send_message(match["joiner_id"], f"😢 Bạn THUA! -{amount:,.0f} Xu\n🪙 Xu: {joiner.coin:,.0f}")
    elif winner == "joiner":
        await context.bot.send_message(match["joiner_id"], f"🎉 Bạn THẮNG! +{amount:,.0f} Xu\n🪙 Xu: {joiner.coin:,.0f}")
        await context.bot.send_message(match["creator_id"], f"😢 Bạn THUA! -{amount:,.0f} Xu\n🪙 Xu: {creator.coin:,.0f}")
    else:
        await context.bot.send_message(match["creator_id"], f"🤝 HÒA! Không ai mất Xu")
        await context.bot.send_message(match["joiner_id"], f"🤝 HÒA! Không ai mất Xu")
    
    # Xóa trận đấu
    del ACTIVE_RPS_MATCHES[msg_id]
    db.close()

# === ĐĂNG KÝ HANDLERS ===
bot_app = Application.builder().token(TOKEN).build()
bot_app.add_handler(CommandHandler("start", start_command))
bot_app.add_handler(CommandHandler("me", me_command))
bot_app.add_handler(CommandHandler("top", top_command))
bot_app.add_handler(CommandHandler("qr", qr_command))
bot_app.add_handler(CommandHandler("admin", admin_dashboard))
bot_app.add_handler(CommandHandler("thong_bao", broadcast_command))
bot_app.add_handler(CommandHandler("view_review", handle_admin_logic))
bot_app.add_handler(CommandHandler("reset_review", handle_admin_logic))
bot_app.add_handler(MessageHandler(filters.Regex(r"^/(tip|fine|del|tipxu|finex)_"), quick_action_handler))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_logic))
bot_app.add_handler(CommandHandler("game", game_ui_command))
bot_app.add_handler(CommandHandler("tx", game_ui_command))
bot_app.add_handler(CommandHandler("pk", game_ui_command))
bot_app.add_handler(CommandHandler("diemdanh", daily_command))
bot_app.add_handler(CommandHandler("shop", shop_command))
bot_app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))
bot_app.add_handler(CommandHandler("order", order_command))
bot_app.add_handler(CommandHandler("dangky", dangky_command))
bot_app.add_handler(CommandHandler("dsnv", dsnv_command))
bot_app.add_handler(CommandHandler("xoanv", xoanv_command))
bot_app.add_handler(CommandHandler("slot", slot_command))
bot_app.add_handler(CommandHandler("kbb", kbb_command))
bot_app.add_handler(CommandHandler("gift", gift_command))
bot_app.add_handler(CommandHandler("qua", gift_command))
# === CALLBACK HANDLERS - CÓ PATTERN TRƯỚC ===
bot_app.add_handler(CallbackQueryHandler(order_button_callback, pattern="^(cancel_order_|pos_done)"))
bot_app.add_handler(CallbackQueryHandler(handle_slot_play, pattern="^slot_play_"))
bot_app.add_handler(CallbackQueryHandler(handle_slot_menu, pattern="^slot_menu$"))
bot_app.add_handler(CallbackQueryHandler(handle_kbb_create, pattern="^kbb_create_"))
bot_app.add_handler(CallbackQueryHandler(handle_kbb_join, pattern="^kbb_join$"))
bot_app.add_handler(CallbackQueryHandler(handle_kbb_choose, pattern="^kbb_choose_"))

# === CALLBACK HANDLER TỔNG QUÁT - ĐỂ CUỐI CÙNG ===
bot_app.add_handler(CallbackQueryHandler(handle_game_buttons))
@asynccontextmanager
async def lifespan(app: FastAPI):
    await bot_app.initialize()
    await bot_app.start()
    
    # 1. Xóa MenuButton cũ (nếu có) để quay về nút "Menu" mặc định
    from telegram import MenuButtonCommands
    await bot_app.bot.set_chat_menu_button(menu_button=MenuButtonCommands())

    # 2. Cài đặt lại danh sách lệnh khi bấm vào nút Menu
    await bot_app.bot.set_my_commands([
    BotCommand("start", "🏠 Về Menu chính"),
    BotCommand("dangky", "📝 Đăng ký nhân viên"),  # <-- THÊM
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

async def run_announcement_scheduler():
    '''Scheduler gửi thông báo 8h và 17h'''
    import pytz
    
    vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    
    while True:
        now = datetime.now(vn_tz)
        
        # Tính thời gian đến 8h sáng
        next_8am = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if now.hour >= 8:
            next_8am += timedelta(days=1)
        
        # Tính thời gian đến 17h chiều
        next_5pm = now.replace(hour=17, minute=0, second=0, microsecond=0)
        if now.hour >= 17:
            next_5pm += timedelta(days=1)
        
        # Chọn thời điểm gần nhất
        if next_8am < next_5pm:
            wait_seconds = (next_8am - now).total_seconds()
            is_morning = True
        else:
            wait_seconds = (next_5pm - now).total_seconds()
            is_morning = False
        
        print(f"⏰ Chờ {wait_seconds/3600:.1f}h để gửi thông báo {'sáng' if is_morning else 'chiều'}")
        
        # Chờ đến giờ
        await asyncio.sleep(wait_seconds)
        
        # Gửi thông báo
        messages = MORNING_MESSAGES if is_morning else EVENING_MESSAGES
        text = random.choice(messages)
        
        try:
            sent_msg = await bot_app.bot.send_message(
                chat_id=MAIN_GROUP_ID,
                message_thread_id=CHAT_TOPIC_ID,
                text=text,
                parse_mode="HTML"
            )
            
            DAILY_ANNOUNCEMENT_MSG[sent_msg.message_id] = set()
            print(f"✅ Đã gửi thông báo {'sáng' if is_morning else 'chiều'}")
            
        except Exception as e:
            print(f"❌ Lỗi gửi thông báo: {e}")
        
        # Chờ 1 phút tránh gửi trùng
        await asyncio.sleep(60)

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.head("/ping")
@app.get("/ping")
def ping(): return {"status": "ok", "message": "Bot is alive!"}

@app.head("/") 
@app.get("/", response_class=HTMLResponse)
def home(request: Request, ref: str = None):
    emoji = ""
    if ref:
        db = SessionLocal()
        emp = db.query(Employee).filter(Employee.telegram_id == ref).first()
        if emp: emoji = emp.emoji
        db.close()
    maps_url = "https://www.google.com/maps/place/KH%E1%BB%88+MILKTEA+%26+MACCHIATO/@9.5996676,105.9736035,17z/data=!4m6!3m5!1s0x31a04df7049cd473:0xc085b8838ce2b39!8m2!3d9.5996676!4d105.9736035!16s%2Fg%2F11jx4pcl6m?hl=vi"
    return templates.TemplateResponse("index.html", {"request": request, "maps_url": maps_url, "staff_emoji": emoji})

@app.get("/webapp", response_class=HTMLResponse)
async def webapp(request: Request):
    return templates.TemplateResponse("webapp.html", {"request": request})

@app.get("/order", response_class=HTMLResponse)
async def webapp_standalone(request: Request):
    return templates.TemplateResponse("webapp_standalone.html", {"request": request})
# --- API ĐỂ WEBAPP GỬI ORDER TRỰC TIẾP (KHÔNG CẦN QUA TELEGRAM) ---

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
    staff_pin: str  # <-- THÊM DÒNG NÀY
    items: List[OrderItem]
    total: int


@app.post("/api/submit_order")
async def submit_order(order: OrderData):
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

        # Nút bấm: HỦY (chỉ người tạo), ĐÃ NHẬP MÁY (ai cũng được)
        kb = [
            [
                InlineKeyboardButton("❌ HỦY", callback_data=f"cancel_order_{staff_telegram_id}"),
                InlineKeyboardButton("✅ ĐÃ NHẬP MÁY", callback_data="pos_done")
            ]
        ]
        
        await bot_app.bot.send_message(
            chat_id=MAIN_GROUP_ID,
            message_thread_id=ORDER_TOPIC_ID,
            text=msg, 
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="HTML"
        )
        
        return {"success": True, "message": "Đã gửi order thành công!"}
        
    except Exception as e:
        return {"success": False, "message": str(e)}
    
@app.post("/api/verify_pin")
async def verify_pin(request: Request):
    try:
        data = await request.json()
        pin = str(data.get("pin", ""))
        
        staff = get_staff_by_pin(pin)
        
        if not staff:
            return {"success": False, "message": "Mã PIN không tồn tại!"}
        
        return {
            "success": True,
            "staff": {
                "name": staff.get("Tên"),
                "phone": staff.get("SĐT"),
                "pin": pin
            }
        }
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
        "Trà trái cây tươi mát, uống là nghiền. Sẽ quay lại!"
    ])
    return {"content": content}

























