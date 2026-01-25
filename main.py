import os
import random
import asyncio
import io
import time
import json
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
from datetime import datetime, date # <--- Thêm cái này để tính ngày giờ
from sqlalchemy import desc
from sqlalchemy.sql import func  
from PIL import Image, ImageDraw, ImageFont

# --- CẤU HÌNH ---
TOKEN = os.environ.get("TELEGRAM_TOKEN") 
ADMIN_ID = "1587932557"
WEB_URL = "https://trasuakhi.onrender.com" 
MAIN_GROUP_ID = -1003566594243
GROUP_INVITE_LINK = "https://t.me/c/3566594243/2"
SPAM_TRACKER = {}

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
            InlineKeyboardButton("🎲 TÀI XỈU (Solo)", callback_data="menu_tx"),
            InlineKeyboardButton("🥊 ĐẤU PK (Solo)", callback_data="menu_pk")
        ],
        [InlineKeyboardButton("❌ Đóng Menu", callback_data="close_menu")]
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

    if data == "pos_done":
        # Khi thu ngân bấm, sửa tin nhắn thêm chữ [ĐÃ XỬ LÝ] và xóa nút bấm
        original_text = query.message.text_html
        new_text = f"<s>{original_text}</s>\n\n✅ <b>THU NGÂN ĐÃ NHẬP MÁY</b>"
        await query.edit_message_text(text=new_text, parse_mode="HTML", reply_markup=None)
        await query.answer("Đã đánh dấu hoàn thành!")
        return

    # --- NHÓM 1: ĐIỀU HƯỚNG ---
    if data == "close_menu":
        await query.delete_message()
        return

    if data == "back_home":
        await game_ui_command(update, context)
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
            [InlineKeyboardButton("❌ Đóng", callback_data="close_menu")]
        ]
        
        # Sửa tin nhắn hiện tại thành Menu chọn tiền
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
    if not await check_private(update, context): return
    user = update.effective_user
    db = SessionLocal()
    emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
    
    if not emp:
        await update.message.reply_text("⚠️ Chưa đăng ký! Gõ /start trước.")
        db.close(); return

    # Kiểm tra xem hôm nay đã điểm danh chưa
    now = datetime.now()
    if emp.last_daily and emp.last_daily.date() == now.date():
        await update.message.reply_text(f"🛑 <b>{emp.name}</b> ơi, nay điểm danh rồi!\nQuay lại vào ngày mai nhé.", parse_mode="HTML")
    else:
        bonus = 10000 # 10k Xu
        emp.coin += bonus
        emp.last_daily = now
        db.commit()
        await update.message.reply_text(
            f"✅ <b>ĐIỂM DANH THÀNH CÔNG!</b>\n"
            f"👤 {emp.name}\n"
            f"🎁 Nhận: <b>+{bonus:,} Xu</b>\n"
            f"💰 Tổng Xu: {emp.coin:,.0f} Xu\n"
            f"👉 Gõ /shop để tiêu Xu.", 
            parse_mode="HTML"
        )
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
        msg = f"🔔 <b>ĐƠN: {customer.upper()}</b> (từ {user.first_name})\n"
        msg += "━━━━━━━━━━━━━━━━━━\n"
        
        for item in items:
            # Gom topping và ghi chú vào ngoặc đơn
            extra = []
            if item.get('tops'):
                extra.extend([t['name'] for t in item['tops']])
            if item.get('notes'):
                extra.extend(item['notes'])
            
            detail = f" ({', '.join(extra)})" if extra else ""
            msg += f"• {item['qty']}x <b>{item['name']}</b>{detail}\n"
        
        msg += f"━━━━━━━━━━━━━━━━━━\n"
        msg += f"💰 <b>TỔNG: {total/1000:,.0f}k</b>" # Hiển thị dạng 79k cho gọn

        # Nút bấm để thu ngân xác nhận đã nhập máy
        kb = [[InlineKeyboardButton("✅ ĐÃ NHẬP MÁY", callback_data="pos_done")]]
        
        await context.bot.send_message(
            chat_id=MAIN_GROUP_ID, 
            text=msg, 
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Lỗi WebApp Data: {e}")

# --- WEB & MAIN ---
bot_app = Application.builder().token(TOKEN).build()
bot_app.add_handler(CommandHandler("start", start_command))
bot_app.add_handler(CommandHandler("me", me_command))
bot_app.add_handler(CommandHandler("top", top_command))
bot_app.add_handler(CommandHandler("qr", qr_command)) # Đã thêm lệnh QR
bot_app.add_handler(CommandHandler("admin", admin_dashboard))
bot_app.add_handler(CommandHandler("thong_bao", broadcast_command))
bot_app.add_handler(CommandHandler("view_review", handle_admin_logic))
bot_app.add_handler(CommandHandler("reset_review", handle_admin_logic))
bot_app.add_handler(MessageHandler(filters.Regex(r"^/(tip|fine|del|tipxu|finex)_"), quick_action_handler))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_logic))
bot_app.add_handler(CommandHandler("game", game_ui_command))     # Lệnh mở Menu
bot_app.add_handler(CommandHandler("tx", game_ui_command))       # Lối tắt cho TX
bot_app.add_handler(CommandHandler("pk", game_ui_command))       # Lối tắt cho PK
bot_app.add_handler(CallbackQueryHandler(handle_game_buttons))   # Xử lý toàn bộ nút bấm
bot_app.add_handler(CommandHandler("diemdanh", daily_command)) # <--- Mới
bot_app.add_handler(CommandHandler("shop", shop_command))      # <--- Mới
bot_app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))
bot_app.add_handler(CommandHandler("order", order_command))

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
        BotCommand("order", "⚡ Mở Menu Order"),
        BotCommand("me", "💳 Ví & Thẻ"),
        BotCommand("game", "🎰 Chơi Game"),
        BotCommand("diemdanh", "📅 Điểm danh"),
        BotCommand("shop", "🛒 Shop quà"),
        BotCommand("qr", "🚀 Lấy mã QR"),
        BotCommand("top", "🏆 BXH"),
    ])
    
    asyncio.create_task(bot_app.updater.start_polling())
    print("✅ Bot đã khởi động với Menu chuẩn...")
    yield
    await bot_app.updater.stop()
    await bot_app.stop()
    await bot_app.shutdown()

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


















