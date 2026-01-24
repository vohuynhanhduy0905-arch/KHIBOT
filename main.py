import os
import random
import asyncio
import io
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
# --- CẬP NHẬT IMPORT (Dòng 8-15) ---
from telegram import (
    Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, BotCommand, 
    InlineKeyboardButton, InlineKeyboardMarkup # <--- MỚI
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes, 
    CallbackQueryHandler # <--- MỚI
)
from database import SessionLocal, Employee, ReviewLog, Review, init_db
from sqlalchemy import desc
from sqlalchemy.sql import func  
from PIL import Image, ImageDraw, ImageFont

# --- CẤU HÌNH ---
TOKEN = os.environ.get("TELEGRAM_TOKEN") 
ADMIN_ID = "1587932557"
WEB_URL = "https://trasuakhi.onrender.com" 
MAIN_GROUP_ID = -1003566594243

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
    
# --- HÀM VẼ THẺ NHÂN VIÊN (ĐÃ SỬA LỖI) ---
def create_card_image(name, emoji, balance, avatar_bytes=None):
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

    # 4. Load Font
    try:
        font_name = ImageFont.truetype("static/font.ttf", 65) 
        font_rank = ImageFont.truetype("static/font.ttf", 35)
        font_money = ImageFont.truetype("static/font.ttf", 60)
    except:
        font_name = ImageFont.load_default()
        font_rank = ImageFont.load_default()
        font_money = ImageFont.load_default()

    # 5. Lấy tên Rank (GỌI HÀM, KHÔNG DÙNG IF THỦ CÔNG)
    rank_name, _ = get_rank_info(balance)

    # 6. Căn giữa
    def draw_centered(y, text, font, color):
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
        except:
            text_width = font.getlength(text)
        x = (W - text_width) / 2
        draw.text((x, y), text, font=font, fill=color)

    # 7. Viết chữ
    draw_centered(230, name, font_name, "white")
    draw_centered(310, f"{rank_name}", font_rank, "#F4D03F") 
    draw_centered(370, f"Ví: {balance:,.0f}đ", font_money, "white")

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

    if data == "menu_pk":
        if chat_type == "private":
            await query.edit_message_text("🥊 <b>PK ĐỐI KHÁNG</b>\nVào nhóm chung để tạo kèo nhé!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Quay lại", callback_data="back_home")]]), parse_mode="HTML")
            return
            
        txt = "🥊 <b>SÀN ĐẤU PK 1vs1</b>\nTiền cược sẽ bị trừ ngay khi tạo kèo.\n👇 <b>Chọn mức tiền thách đấu:</b>"
        kb = [[InlineKeyboardButton("⚡ 2k", callback_data="pk_create_2000"), InlineKeyboardButton("⚡ 5k", callback_data="pk_create_5000"), InlineKeyboardButton("⚡ 10k", callback_data="pk_create_10000"), InlineKeyboardButton("⚡ 20k", callback_data="pk_create_20000")], [InlineKeyboardButton("❌ Đóng", callback_data="close_menu")]]
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return

    # --- NHÓM 2: TÀI XỈU ---
    if data.startswith("tx_chon_"):
        choice = "XỈU" if "xiu" in data else "TÀI"
        code = "xiu" if "xiu" in data else "tai"
        txt = f"Bạn chọn: <b>{choice}</b>\n💰 Cược nhiu ní:"
        kb = [[InlineKeyboardButton("1k", callback_data=f"tx_play_{code}_1000"), InlineKeyboardButton("2k", callback_data=f"tx_play_{code}_2000"), InlineKeyboardButton("5k", callback_data=f"tx_play_{code}_5000"), InlineKeyboardButton("10k", callback_data=f"tx_play_{code}_10000")], [InlineKeyboardButton("🔙 Chọn lại", callback_data="menu_tx")]]
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return

    if data.startswith("tx_play_"):
        try:
            # Xóa menu cũ
            try: await query.message.delete()
            except: pass

            parts = data.split("_")
            choice_code = parts[2]
            amount = int(parts[3])
            db = SessionLocal()
            emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
            
            if not emp or emp.balance < amount: 
                await context.bot.send_message(user.id, "💸 Không đủ tiền!")
                db.close(); return

            emp.balance -= amount
            db.commit()

            # Tung xúc xắc
            msg_wait = await context.bot.send_message(chat_id=query.message.chat_id, text=f"🎲 Đang tung ({amount:,.0f}đ)...")
            m1 = await context.bot.send_dice(chat_id=query.message.chat_id)
            m2 = await context.bot.send_dice(chat_id=query.message.chat_id)
            m3 = await context.bot.send_dice(chat_id=query.message.chat_id)
            
            d1, d2, d3 = m1.dice.value, m2.dice.value, m3.dice.value
            total = d1 + d2 + d3
            result_str = "XỈU" if total <= 10 else "TÀI"

            await asyncio.sleep(3.5) # Chờ quay
            
            # Tính toán
            is_win = False
            if d1 == d2 == d3: note = f"⛈️ <b>BÃO {d1}! (Thua sạch)</b>"
            elif (choice_code == "xiu" and total <= 10) or (choice_code == "tai" and total > 10):
                profit = int(amount * 0.85)
                emp.balance += (amount + profit)
                note = f"✅ <b>THẮNG!</b> (+{profit:,.0f}đ)"
            else: note = f"❌ <b>THUA!</b> (-{amount:,.0f}đ)"
            
            db.commit()

            # Gửi kết quả
            final_msg = f"📊 Kết quả: [{d1}] [{d2}] [{d3}] = <b>{total}</b> ({result_str})\n{note}\n💰 Ví: {emp.balance:,.0f}đ"
            kb = [[InlineKeyboardButton("🔄 Chơi tiếp", callback_data="menu_tx")]]
            await context.bot.send_message(chat_id=query.message.chat_id, text=final_msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

            # --- XÓA XÚC XẮC NGAY LẬP TỨC ---
            for m in [msg_wait, m1, m2, m3]:
                try: await m.delete()
                except: pass

        except Exception as e: print(e)
        finally: db.close()
        return

    # --- LOGIC TẠO KÈO (Người chơi bấm ở Chat Riêng -> Bot gửi vào Nhóm) ---
    if data.startswith("pk_create_"):
        amount = int(data.split("_")[-1])
        db = SessionLocal()
        emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
        
        # Kiểm tra tiền
        if not emp or emp.balance < amount: 
            await query.answer("💸 Không đủ tiền!", show_alert=True)
            db.close(); return
            
        # 1. Báo thành công ở chat riêng
        await query.edit_message_text(f"✅ Đã gửi lời thách đấu <b>{amount:,.0f}đ</b> vào nhóm!", parse_mode="HTML")

        # 2. Gửi Lời mời vào NHÓM CHUNG (MAIN_GROUP_ID)
        kb = [[InlineKeyboardButton("🥊 NHẬN KÈO NGAY", callback_data="pk_join")]]
        msg_content = (
            f"🔥 <b>PK THÁCH ĐẤU</b> 🔥\n"
            f"👤 <b>{emp.name}</b> đang tìm đối thủ!\n"
            f"💰 Cược: <b>{amount:,.0f}đ</b>\n"
            f"👇 <i>Ai dám nhận không?</i>"
        )
        try:
            # Gửi tin nhắn vào nhóm
            sent_msg = await context.bot.send_message(chat_id=MAIN_GROUP_ID, text=msg_content, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
            
            # Lưu thông tin kèo
            ACTIVE_PK_MATCHES[sent_msg.message_id] = {
                "creator_id": str(user.id), 
                "creator_name": emp.name, 
                "amount": amount
            }
        except Exception as e:
            await context.bot.send_message(user.id, f"⚠️ Lỗi: Chưa thêm Bot vào nhóm hoặc sai ID nhóm!\n({e})")

        db.close(); return

    # --- LOGIC NHẬN KÈO (Người khác bấm ở Nhóm -> Chơi -> Xóa -> Báo riêng) ---
    if data == "pk_join":
        invite_msg_id = query.message.message_id
        group_chat_id = query.message.chat_id # Đây chính là ID nhóm
        
        match_info = ACTIVE_PK_MATCHES.get(invite_msg_id)
        if not match_info: await query.answer("❌ Kèo đã hủy hoặc có người nhận rồi!", show_alert=True); return
            
        challenger_id = str(user.id)
        creator_id = match_info["creator_id"]
        amount = match_info["amount"]
        
        if challenger_id == creator_id: await query.answer("🚫 Đừng tự chơi với mình!", show_alert=True); return
            
        db = SessionLocal()
        p1 = db.query(Employee).filter(Employee.telegram_id == creator_id).first() # Chủ kèo
        p2 = db.query(Employee).filter(Employee.telegram_id == challenger_id).first() # Người nhận
        
        if not p2 or p2.balance < amount: await query.answer("💸 Bạn không đủ tiền!", show_alert=True); db.close(); return
        if p1.balance < amount: await query.answer("❌ Chủ kèo hết tiền!", show_alert=True); db.close(); return

        # Trừ tiền
        p1.balance -= amount; p2.balance -= amount
        db.commit()

        # Xóa kèo khỏi danh sách để không ai bấm nữa
        if invite_msg_id in ACTIVE_PK_MATCHES: del ACTIVE_PK_MATCHES[invite_msg_id]

        # 1. Bắt đầu tung xúc xắc TẠI NHÓM (Cho mọi người xem)
        start_msg = await context.bot.send_message(group_chat_id, f"🥊 <b>TRẬN ĐẤU BẮT ĐẦU!</b>\n🔴 {match_info['creator_name']} VS 🔵 {p2.name}", parse_mode="HTML")
        
        m1 = await context.bot.send_dice(group_chat_id) # P1 tung
        d1 = m1.dice.value
        await asyncio.sleep(2)
        
        m2 = await context.bot.send_dice(group_chat_id) # P2 tung
        d2 = m2.dice.value
        await asyncio.sleep(3.5)

        # 2. Tính kết quả
        total_pot = amount * 2; fee = int(total_pot * 0.05); prize = total_pot - fee
        result_txt = f"🥊 <b>KẾT QUẢ PK</b> ({amount:,.0f}đ)\n"
        winner_id = None
        
        if d1 > d2: 
            p1.balance += prize; winner_id = p1.telegram_id
            result_txt += f"🔴 {match_info['creator_name']}: {d1} 🏆 <b>THẮNG</b>\n🔵 {p2.name}: {d2}\n💰 +{prize:,.0f}đ"
        elif d2 > d1: 
            p2.balance += prize; winner_id = p2.telegram_id
            result_txt += f"🔴 {match_info['creator_name']}: {d1}\n🔵 {p2.name}: {d2} 🏆 <b>THẮNG</b>\n💰 +{prize:,.0f}đ"
        else: 
            p1.balance += amount; p2.balance += amount
            result_txt += f"🔴 {match_info['creator_name']}: {d1}\n🔵 {p2.name}: {d2}\n🤝 <b>HÒA!</b> Hoàn tiền."

        db.commit()
        
        # 3. Hiện kết quả tại NHÓM
        result_msg = await context.bot.send_message(group_chat_id, result_txt, parse_mode="HTML")
        
        # 4. Gửi kết quả RIÊNG TƯ về bot cho 2 người chơi (Để lưu lại bằng chứng)
        private_log = f"{result_txt}\n➖➖➖➖➖➖\n💰 Số dư hiện tại: "
        try: await context.bot.send_message(creator_id, private_log + f"{p1.balance:,.0f}đ", parse_mode="HTML")
        except: pass # Phòng trường hợp user block bot
        
        try: await context.bot.send_message(challenger_id, private_log + f"{p2.balance:,.0f}đ", parse_mode="HTML")
        except: pass

        # 5. Đợi 10 giây rồi XÓA SẠCH ở nhóm (Yêu cầu của bạn)
        await asyncio.sleep(10)
        messages_to_delete = [invite_msg_id, start_msg.message_id, m1.message_id, m2.message_id, result_msg.message_id]
        
        for mid in messages_to_delete:
            try: await context.bot.delete_message(chat_id=group_chat_id, message_id=mid)
            except: pass
            
        db.close()
        return

# --- CÁC LỆNH BOT ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    msg = f"Chào <b>{emp.name}</b>!\nMã của bạn: {emp.emoji}\nLink khách: {link}"
    await update.message.reply_photo(qr_api, caption=msg, parse_mode="HTML")
    db.close()

async def me_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = SessionLocal()
    emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
    
    if emp:
        # Gửi tin nhắn chờ
        wait_msg = await update.message.reply_text("📸 Đợi cái ní, đang lấy avt để in thẻ...")
        
        # Lấy Avatar
        avatar_io = None
        try:
            photos = await user.get_profile_photos(limit=1)
            if photos.total_count > 0:
                photo_file = await photos.photos[0][-1].get_file()
                avatar_bytes = await photo_file.download_as_bytearray()
                avatar_io = io.BytesIO(avatar_bytes)
        except: pass

        # Vẽ ảnh (Chạy ngầm để không lag bot)
        loop = asyncio.get_running_loop()
        photo_file = await loop.run_in_executor(None, create_card_image, emp.name, emp.emoji, emp.balance, avatar_io)

        # Lấy thông tin Rank để viết Caption
        rank_name, rank_icon = get_rank_info(emp.balance)

        # Lịch sử
        logs = db.query(ReviewLog).filter(ReviewLog.staff_id == str(user.id)).order_by(desc(ReviewLog.created_at)).limit(5).all()
        history = "\n".join([f"{l.stars}⭐: {l.reviewer_name}" for l in logs]) if logs else "   (Chưa có review nào)"
        
        caption = (
            f"💳 <b>THẺ NHÂN VIÊN</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👤 <b>Cấp bậc:</b> {rank_icon} {rank_name}\n"
            f"💰 <b>Số dư ví:</b> {emp.balance:,.0f}đ\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🕒 <b>Lịch sử hoạt động:</b>\n"
            f"{history}\n\n"
            f"👉 <i>Quét mã QR để tích điểm ngay!</i>"
        )

        await update.message.reply_photo(photo=photo_file, caption=caption, parse_mode="HTML")
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=wait_msg.message_id)
        
    else:
        await update.message.reply_text("Chưa đăng ký. Bấm /start")
    
    db.close()

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    top = db.query(Employee).order_by(desc(Employee.balance)).limit(10).all()
    msg = "🏆 BẢNG XẾP HẠNG 🏆\n"
    for i, emp in enumerate(top, 1):
        msg += f"{i}. {emp.name} ({emp.emoji}): {emp.balance:,.0f}đ\n"
    await update.message.reply_text(msg)
    db.close()

async def qr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    link = f"{WEB_URL}/?ref={user_id}"
    qr_api = f"https://api.qrserver.com/v1/create-qr-code/?size=500x500&data={link}"
    await update.message.reply_photo(photo=qr_api, caption="🚀 <b>Mã QR Tốc Độ Cao</b>\nĐưa khách quét ngay!", parse_mode="HTML")

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
    user_id = str(update.effective_user.id)
    text = update.message.text
    if user_id != ADMIN_ID: return

    admin_buttons = ["📋 Danh Sách NV", "📢 Gửi Thông Báo", "🔄 Reset Toàn Bộ", "❌ Thoát Admin", "📝 Xem Kho Review", "🗑 Xóa Hết Review"]
    if text not in admin_buttons:
        await handle_add_review(update, context)
        return

    db = SessionLocal()
    if text == "📋 Danh Sách NV":
        emps = db.query(Employee).all()
        msg = "📋 <b>QUẢN LÝ NHÂN VIÊN</b>\n\n" + "".join([f"👤 {e.name} ({e.emoji}) | {e.balance:,.0f}đ\n👉 /tip_{e.telegram_id} | /fine_{e.telegram_id} | /del_{e.telegram_id}\n---\n" for e in emps]) if emps else "Chưa có NV."
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
    action, target_id = command[1:].split('_') 
    db = SessionLocal()
    emp = db.query(Employee).filter(Employee.telegram_id == target_id).first()
    if emp:
        if action == "tip": emp.balance += 5000; await update.message.reply_text(f"✅ Thưởng 5k {emp.name}.")
        elif action == "fine": emp.balance -= 5000; await update.message.reply_text(f"✅ Phạt 5k {emp.name}.")
        #elif action == "del": db.delete(emp); await update.message.reply_text(f"🗑 Đã xóa.")
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
bot_app.add_handler(MessageHandler(filters.Regex(r"^/(tip|fine|del)_"), quick_action_handler))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_logic))
bot_app.add_handler(CommandHandler("game", game_ui_command))     # Lệnh mở Menu
bot_app.add_handler(CommandHandler("tx", game_ui_command))       # Lối tắt cho TX
bot_app.add_handler(CommandHandler("pk", game_ui_command))       # Lối tắt cho PK
bot_app.add_handler(CallbackQueryHandler(handle_game_buttons))   # Xử lý toàn bộ nút bấm


@asynccontextmanager
async def lifespan(app: FastAPI):
    await bot_app.initialize()
    await bot_app.start()
    
    # Cài đặt Menu tự động
    await bot_app.bot.set_my_commands([
        BotCommand("me", "💳 Ví & Thẻ"),
        BotCommand("game", "🎰 Chơi Game (TX/PK)"),  # <-- Mới
        BotCommand("qr", "🚀 Lấy mã QR"),
        BotCommand("top", "🏆 BXH Đại gia"),
    ])
    
    #await bot_app.updater.start_polling()
    asyncio.create_task(bot_app.updater.start_polling())
    
    print("✅ Bot đã khởi động ngầm...")
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







