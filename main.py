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

# --- IMPORT TELEGRAM CHUẨN V21.9 ---
from telegram import (
    Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, BotCommand, 
    InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions, WebAppInfo,
    KeyboardButton, MenuButtonCommands
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes, 
    CallbackQueryHandler
)

from database import SessionLocal, Employee, ReviewLog, Review, init_db, ShopLog
from datetime import datetime, date
from sqlalchemy import desc
from sqlalchemy.sql import func  
from PIL import Image, ImageDraw, ImageFont

# --- CẤU HÌNH ---
TOKEN = os.environ.get("TELEGRAM_TOKEN") 
ADMIN_ID = "1587932557"
WEB_URL = "https://trasuakhi.onrender.com" 
MAIN_GROUP_ID = -1003566594243
SPAM_TRACKER = {}

# Setup DB
init_db()
templates = Jinja2Templates(directory="templates")

# List Emoji
EMOJI_POOL = ["🍇", "🍈", "🍉", "🍊", "🍋", "🍌", "🍍", "🥭", "🍎", "🍏", "🍐", "🍑", "🍒", "🍓", "🥝", "🍅", "🥥", "🥑", "🍆", "🥔", "🥕", "🌽", "🌶️", "🥒", "🥬", "🥦", "🧄", "🧅", "🍄", "🥜", "🌰", "🍞", "🥐", "🥖", "🥨", "🥯", "🥞", "🧇", "🧀", "🍖", "🍗", "🥩", "🥓", "🍔", "🍟", "🍕", "🌭", "🥪", "🌮", "🌯", "🥙", "🧆", "🥚", "🍳", "🥘", "🍲", "🥣", "🥗", "🍿", "🧈", "🧂", "🥫", "🍱", "🍘", "🍙", "🍚", "🍛", "🍜", "🍝", "🍠", "🍢", "🍣", "🍤", "🍥", "🥮", "🍡", "🥟", "🥠", "🥡", "🦀", "🦞", "🦐", "🦑", "🦪", "🍦", "🍧", "🍨", "🍩", "🍪", "🎂", "🍰", "🧁", "🥧", "🍫", "🍬", "🍭", "🍮", "🍯", "🍼", "🥛", "☕", "🍵", "🍶", "🍾", "🍷", "🍸", "🍹", "🍺", "🍻", "🥂", "🥃", "🥤", "🧃", "🧉", "🧊", "🥢", "🍽️", "🍴", "🥄"]

# --- HÀM PHỤ TRỢ ---
def crop_to_circle(img):
    mask = Image.new('L', img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + img.size, fill=255)
    output = Image.new('RGBA', img.size, (0, 0, 0, 0))
    output.paste(img, (0, 0), mask)
    return output

def get_rank_info(balance):
    name, icon = "Dân Thường", "🌱" 
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

def get_main_menu():
    keyboard = [
        ["💳 Ví & Thẻ", "📅 Điểm Danh"],
        ["🎰 Giải Trí", "🛒 Shop Xu"],
        [KeyboardButton("⚡ Order Nhanh (Vào Nhóm)", web_app=WebAppInfo(url=f"{WEB_URL}/webapp"))] 
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def create_card_image(name, emoji, balance, coin, avatar_bytes=None):
    W, H = 800, 500
    try:
        img = Image.open("static/card_bg.jpg").convert("RGBA")
        img = img.resize((W, H))
    except:
        img = Image.new('RGBA', (W, H), color='#1A5336')
    draw = ImageDraw.Draw(img)
    try:
        logo = Image.open("static/logo.png").convert("RGBA")
        logo = crop_to_circle(logo.resize((110, 110)))
        img.paste(logo, (W - 140, 30), logo)
    except: pass

    if avatar_bytes:
        try:
            avatar = Image.open(avatar_bytes).convert("RGBA")
            avatar = crop_to_circle(avatar.resize((160, 160)))
            draw.ellipse((W//2 - 82, 38, W//2 + 82, 202), outline="#F4D03F", width=3) 
            img.paste(avatar, (W//2 - 80, 40), avatar)
        except: pass

    try:
        font_name = ImageFont.truetype("static/font.ttf", 60) 
        font_rank = ImageFont.truetype("static/font.ttf", 30)
        font_money = ImageFont.truetype("static/font.ttf", 45)
    except:
        font_name = ImageFont.load_default()
        font_rank = ImageFont.load_default()
        font_money = ImageFont.load_default()

    rank_name, _ = get_rank_info(balance)
    def draw_centered(y, text, font, color):
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
        except: text_width = font.getlength(text)
        draw.text(((W - text_width) / 2, y), text, font=font, fill=color)

    draw_centered(230, name, font_name, "white")
    draw_centered(300, f"{rank_name}", font_rank, "#F4D03F") 
    draw_centered(350, f"Ví: {balance:,.0f}đ", font_money, "white")
    draw_centered(410, f"Xu: {coin:,.0f}", font_money, "#00FF00")

    bio = io.BytesIO()
    bio.name = 'card.png'
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

# --- LOGIC GAME & UTILS ---
ACTIVE_PK_MATCHES = {} 

async def check_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private": return True
    user_id = update.effective_user.id
    try: await update.message.delete()
    except: pass
    
    now = time.time()
    if user_id not in SPAM_TRACKER: SPAM_TRACKER[user_id] = []
    SPAM_TRACKER[user_id] = [t for t in SPAM_TRACKER[user_id] if now - t < 10]
    SPAM_TRACKER[user_id].append(now)
    
    if len(SPAM_TRACKER[user_id]) >= 3:
        try:
            await context.bot.restrict_chat_member(update.effective_chat.id, user_id, ChatPermissions(False), until_date=now + 300)
            msg = await context.bot.send_message(update.effective_chat.id, f"🚫 {update.effective_user.first_name} spam quá nhiều! Bị cấm chat 5 phút.")
            asyncio.create_task(asyncio.sleep(10)); await msg.delete()
        except: pass
        return False
    if len(SPAM_TRACKER[user_id]) == 1:
        msg = await context.bot.send_message(update.effective_chat.id, f"🤫 {update.effective_user.first_name}, ib riêng bot nhé!")
        asyncio.create_task(asyncio.sleep(5)); await msg.delete()
    return False

# --- CÁC COMMANDS ---
async def order_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hàm Order bất tử - chạy được cả trong Topic và Group thường"""
    try:
        chat_id = update.effective_chat.id
        # Lấy thread_id nếu là topic
        thread_id = None
        if update.message and update.message.message_thread_id:
            thread_id = update.message.message_thread_id

        print(f"DEBUG: /order tại {chat_id}, Thread: {thread_id}")

        kb = [[InlineKeyboardButton("⚡ MỞ MENU ORDER ⚡", web_app=WebAppInfo(url=f"{WEB_URL}/webapp"))]]
        
        # Thử Reply trước
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text="👇 Bấm vào nút bên dưới để lên đơn nhé:",
                reply_markup=InlineKeyboardMarkup(kb),
                message_thread_id=thread_id,
                reply_to_message_id=update.message.message_id
            )
        except Exception as e:
            print(f"Lỗi Reply: {e}, thử gửi thường...")
            # Nếu Reply lỗi (do tin nhắn bị xóa hoặc không tìm thấy), gửi tin mới
            await context.bot.send_message(
                chat_id=chat_id,
                text="👇 Bấm vào nút bên dưới để lên đơn nhé:",
                reply_markup=InlineKeyboardMarkup(kb),
                message_thread_id=thread_id
            )
            
    except Exception as e:
        print(f"❌ LỖI NGHIÊM TRỌNG ORDER: {e}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_private(update, context): return
    user = update.effective_user
    db = SessionLocal()
    emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
    if not emp:
        used = [e.emoji for e in db.query(Employee).all()]
        avail = [e for e in EMOJI_POOL if e not in used]
        if not avail: await update.message.reply_text("Hết slot!"); db.close(); return
        emp = Employee(telegram_id=str(user.id), name=user.full_name, emoji=random.choice(avail))
        db.add(emp); db.commit()
    
    msg = f"Chào <b>{emp.name}</b> {emp.emoji}!\nChúc ngày mới tốt lành."
    await update.message.reply_text(msg, reply_markup=get_main_menu(), parse_mode="HTML")
    db.close()

async def me_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_private(update, context): return
    user = update.effective_user
    db = SessionLocal()
    emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
    if emp:
        wait = await update.message.reply_text("📸 Đang in thẻ...")
        avt = None
        try:
            photos = await user.get_profile_photos(limit=1)
            if photos.total_count > 0:
                f = await photos.photos[0][-1].get_file()
                avt = io.BytesIO(await f.download_as_bytearray())
        except: pass
        loop = asyncio.get_running_loop()
        img = await loop.run_in_executor(None, create_card_image, emp.name, emp.emoji, emp.balance, emp.coin, avt)
        rank, icon = get_rank_info(emp.balance)
        cap = f"💳 <b>THẺ NV</b>\n👤 Rank: {icon} {rank}\n💰 Lương: {emp.balance:,.0f}đ\n🪙 Xu: {emp.coin:,.0f}"
        await update.message.reply_photo(img, caption=cap, parse_mode="HTML")
        await wait.delete()
    db.close()

async def game_ui_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        try: await update.message.delete()
        except: pass
        msg = await update.message.reply_text(f"⚠️ {update.effective_user.first_name}, ib riêng bot nha!")
        await asyncio.sleep(5); await msg.delete(); return
    
    msg = f"🎰 <b>GAME CENTER</b>\nĐại gia {update.effective_user.first_name} chơi gì?"
    kb = [[InlineKeyboardButton("🎲 TÀI XỈU", callback_data="menu_tx"), InlineKeyboardButton("🥊 ĐẤU PK", callback_data="menu_pk")], [InlineKeyboardButton("❌ Đóng", callback_data="close_menu")]]
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def handle_game_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user = q.from_user
    data = q.data
    try: await q.answer()
    except: pass

    if data == "pos_done":
        await q.edit_message_text(f"<s>{q.message.text_html}</s>\n\n✅ <b>THU NGÂN ĐÃ NHẬP MÁY</b>", parse_mode="HTML")
        return
    if data == "close_menu": await q.delete_message(); return
    if data == "back_home": await game_ui_command(update, context); return
    
    # --- LOGIC TÀI XỈU ---
    if data == "menu_tx":
        txt = "🎲 <b>TÀI XỈU</b>\n🔴 XỈU: 3-10 | 🔵 TÀI: 11-18\n⚡ Ăn 0.85 | Bão ăn hết"
        kb = [[InlineKeyboardButton("🔴 XỈU", callback_data="tx_chon_xiu"), InlineKeyboardButton("🔵 TÀI", callback_data="tx_chon_tai")], [InlineKeyboardButton("🔙", callback_data="back_home")]]
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML"); return
    
    if data.startswith("tx_chon_"):
        c = "XỈU" if "xiu" in data else "TÀI"
        code = "xiu" if "xiu" in data else "tai"
        kb = [[InlineKeyboardButton("10k", callback_data=f"tx_play_{code}_10000"), InlineKeyboardButton("20k", callback_data=f"tx_play_{code}_20000"), InlineKeyboardButton("50k", callback_data=f"tx_play_{code}_50000")], [InlineKeyboardButton("🔙", callback_data="menu_tx")]]
        await q.edit_message_text(f"Chọn: <b>{c}</b>. Cược bao nhiêu xu?", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML"); return

    if data.startswith("tx_play_"):
        await q.delete_message()
        _, _, code, amt = data.split("_"); amt = int(amt)
        db = SessionLocal(); emp = db.query(Employee).filter(Employee.telegram_id==str(user.id)).first()
        if not emp or emp.coin < amt: await context.bot.send_message(user.id, "💸 Không đủ xu!"); db.close(); return
        emp.coin -= amt; db.commit()
        
        m = await context.bot.send_message(user.id, f"🎲 Tung xúc xắc ({amt:,} xu)...")
        d1, d2, d3 = [ (await context.bot.send_dice(user.id)).dice.value for _ in range(3) ]
        total = d1+d2+d3; res = "XỈU" if total <= 10 else "TÀI"
        await asyncio.sleep(3)
        
        win = False
        if d1==d2==d3: note = f"⛈️ BÃO {d1}! Nhà cái ăn hết."
        elif (code=="xiu" and total<=10) or (code=="tai" and total>10):
            prof = int(amt*0.85); emp.coin += (amt+prof); note=f"✅ THẮNG (+{prof:,} xu)"; win=True
        else: note=f"❌ THUA (-{amt:,} xu)"
        db.commit(); db.close()
        await context.bot.send_message(user.id, f"🎲 KQ: {d1}-{d2}-{d3} = <b>{total}</b> ({res})\n{note}\n🪙 Xu: {emp.coin:,.0f}", parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Chơi lại", callback_data="menu_tx")]]))
        await m.delete(); return

    # --- LOGIC PK ---
    if data == "menu_pk":
        kb = [[InlineKeyboardButton("10k", callback_data="pk_create_10000"), InlineKeyboardButton("20k", callback_data="pk_create_20000"), InlineKeyboardButton("50k", callback_data="pk_create_50000")], [InlineKeyboardButton("❌", callback_data="close_menu")]]
        await q.edit_message_text("🥊 <b>PK 1vs1 (XU)</b>\nChọn mức cược để tạo kèo:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML"); return

    if data.startswith("pk_create_"):
        amt = int(data.split("_")[-1])
        db = SessionLocal(); emp = db.query(Employee).filter(Employee.telegram_id==str(user.id)).first()
        if not emp or emp.coin < amt: await q.answer("Không đủ xu!", show_alert=True); db.close(); return
        
        await q.edit_message_text(f"✅ Đã tạo kèo {amt:,} xu vào nhóm!"); db.close()
        kb = [[InlineKeyboardButton("🥊 NHẬN KÈO", callback_data="pk_join")]]
        cap = f"🔥 <b>PK SOLO ({amt:,} Xu)</b>\n👤 <b>{emp.name}</b> tìm đối thủ!"
        try:
            with open("static/pk_invite.jpg", "rb") as p:
                msg = await context.bot.send_photo(MAIN_GROUP_ID, p, caption=cap, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
                ACTIVE_PK_MATCHES[msg.message_id] = {"cid": str(user.id), "cname": emp.name, "amt": amt}
        except Exception as e: await context.bot.send_message(user.id, f"Lỗi gửi nhóm: {e}")
        return

    if data == "pk_join":
        mid = q.message.message_id; info = ACTIVE_PK_MATCHES.get(mid)
        if not info: await q.answer("❌ Kèo không tồn tại!", show_alert=True); return
        if str(user.id) == info["cid"]: await q.answer("🚫 Không tự chơi được!", show_alert=True); return
        
        db = SessionLocal()
        p1 = db.query(Employee).filter(Employee.telegram_id==info["cid"]).first()
        p2 = db.query(Employee).filter(Employee.telegram_id==str(user.id)).first()
        amt = info["amt"]
        
        if not p2 or p2.coin < amt: await q.answer("💸 Bạn không đủ xu!", show_alert=True); db.close(); return
        if p1.coin < amt: await q.answer("❌ Chủ kèo hết xu!", show_alert=True); db.close(); return
        
        p1.coin -= amt; p2.coin -= amt; db.commit()
        del ACTIVE_PK_MATCHES[mid]
        
        gid = q.message.chat.id
        await context.bot.send_message(gid, f"🥊 <b>BẮT ĐẦU!</b>\n🔴 {info['cname']} vs 🔵 {p2.name}", parse_mode="HTML")
        d1 = (await context.bot.send_dice(gid)).dice.value; await asyncio.sleep(2)
        d2 = (await context.bot.send_dice(gid)).dice.value; await asyncio.sleep(3)
        
        prize = int(amt*1.9) # Phí 5% -> Ăn 1.9
        res = f"🥊 <b>KẾT QUẢ</b>\n"
        if d1 > d2: p1.coin += prize; res += f"🔴 {info['cname']} WIN (+{prize:,})\n🔵 {p2.name} LOSE"
        elif d2 > d1: p2.coin += prize; res += f"🔵 {p2.name} WIN (+{prize:,})\n🔴 {info['cname']} LOSE"
        else: p1.coin += amt; p2.coin += amt; res += "🤝 HÒA (Hoàn tiền)"
        
        db.commit(); db.close()
        rs = await context.bot.send_message(gid, res, parse_mode="HTML")
        await asyncio.sleep(10)
        for m in [mid, rs.message_id]: 
            try: await context.bot.delete_message(gid, m)
            except: pass
        return

    if data.startswith("buy_salary_"):
        vnd = int(data.split("_")[-1]); cost = vnd * 100
        db = SessionLocal(); emp = db.query(Employee).filter(Employee.telegram_id==str(user.id)).first()
        if emp and emp.coin >= cost:
            emp.coin -= cost; emp.balance += vnd
            db.add(ShopLog(staff_id=str(user.id), item_name=f"Đổi {vnd} lương", cost=cost, status="done"))
            db.commit()
            await q.edit_message_text(f"✅ Đổi thành công!\n➖ {cost:,} Xu\n➕ {vnd:,}đ Lương", parse_mode="HTML")
        else: await q.answer("❌ Không đủ xu!", show_alert=True)
        db.close(); return

# --- WEB APP & ADMIN HANDLERS ---
async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = json.loads(update.effective_message.web_app_data.data)
        user = update.effective_user
        msg = f"🔔 <b>ĐƠN: {data.get('customer','Khách').upper()}</b> (từ {user.first_name})\n━━━━━━━━━\n"
        for i in data.get('items', []):
            extra = []
            if i.get('tops'): extra.extend([t['name'] for t in i['tops']])
            if i.get('notes'): extra.extend(i['notes'])
            det = f" ({', '.join(extra)})" if extra else ""
            msg += f"• {i['qty']}x <b>{i['name']}</b>{det}\n"
        msg += f"━━━━━━━━━\n💰 <b>TỔNG: {data.get('total',0)/1000:,.0f}k</b>"
        await context.bot.send_message(MAIN_GROUP_ID, msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ ĐÃ NHẬP MÁY", callback_data="pos_done")]]), parse_mode="HTML")
    except Exception as e: print(f"Lỗi WebApp: {e}")

async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID: return
    kb = [["📋 Danh Sách NV", "📢 Gửi Thông Báo"], ["📝 Xem Review", "🗑 Xóa Review"], ["🔄 Reset Ví", "❌ Thoát"]]
    await update.message.reply_text("🔓 ADMIN MENU", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == "💳 Ví & Thẻ": await me_command(update, context); return
    if txt == "📅 Điểm Danh": await daily_command(update, context); return
    if txt == "🎰 Giải Trí": await game_ui_command(update, context); return
    if txt == "🛒 Shop Xu": await shop_command(update, context); return
    if txt == "🏆 BXH Đại Gia": await top_command(update, context); return
    if txt == "🚀 Lấy mã QR": await qr_command(update, context); return
    
    # Nút bấm mở WebApp trên bàn phím:
    if "Order Nhanh" in txt:
        # Nếu người dùng bấm nút trên bàn phím, ta cũng gọi hàm order để nó gửi nút inline
        await order_command(update, context) 
        return

    # Admin Logic
    if str(update.effective_user.id) == ADMIN_ID:
        db = SessionLocal()
        if txt == "📋 Danh Sách NV":
            msg = "\n".join([f"{e.name}: {e.balance:,.0f}đ | {e.coin:,.0f}xu (/tip_{e.telegram_id})" for e in db.query(Employee).all()])
            await update.message.reply_text(msg[:4000] if msg else "Trống")
        elif txt == "📝 Xem Review":
            msg = "\n".join([r.content for r in db.query(Review).all()])
            await update.message.reply_text(msg[:4000] if msg else "Trống")
        elif txt == "🗑 Xóa Review": db.query(Review).delete(); db.commit(); await update.message.reply_text("Đã xóa")
        elif txt == "🔄 Reset Ví": db.query(Employee).update({Employee.balance:0}); db.commit(); await update.message.reply_text("Done")
        elif txt == "❌ Thoát": await update.message.reply_text("Bye", reply_markup=ReplyKeyboardRemove())
        else: db.add(Review(content=txt)); db.commit(); await update.message.reply_text("✅ Đã lưu review")
        db.close()

async def daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_private(update, context): return
    db = SessionLocal(); emp = db.query(Employee).filter(Employee.telegram_id==str(update.effective_user.id)).first()
    if not emp: await update.message.reply_text("Chưa đăng ký!"); db.close(); return
    
    if emp.last_daily and emp.last_daily.date() == datetime.now().date():
        await update.message.reply_text("Nay nhận rồi mai quay lại nha!"); db.close(); return
    
    emp.coin += 10000; emp.last_daily = datetime.now(); db.commit()
    await update.message.reply_text(f"✅ Điểm danh: +10k Xu\nTổng: {emp.coin:,} Xu")
    db.close()

async def shop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_private(update, context): return
    kb = [[InlineKeyboardButton("💸 1k Lương (100k Xu)", callback_data="buy_salary_1000")], [InlineKeyboardButton("❌ Đóng", callback_data="close_menu")]]
    await update.message.reply_text("🛒 SHOP XU", reply_markup=InlineKeyboardMarkup(kb))

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_private(update, context): return
    db = SessionLocal()
    msg = "🏆 TOP LƯƠNG:\n" + "\n".join([f"{i+1}. {e.name}: {e.balance:,.0f}đ" for i,e in enumerate(db.query(Employee).order_by(desc(Employee.balance)).limit(5))])
    msg += "\n\n🪙 TOP XU:\n" + "\n".join([f"{i+1}. {e.name}: {e.coin:,.0f}" for i,e in enumerate(db.query(Employee).order_by(desc(Employee.coin)).limit(5))])
    await update.message.reply_text(msg); db.close()

async def qr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_photo(f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={WEB_URL}/?ref={uid}", caption="Mã QR của bạn")

async def quick_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID: return
    act, tid = update.message.text[1:].split('_')
    db = SessionLocal(); emp = db.query(Employee).filter(Employee.telegram_id==tid).first()
    if emp:
        if act=="tip": emp.balance+=5000; t="Thưởng 5k"
        if act=="fine": emp.balance-=5000; t="Phạt 5k"
        if act=="tipxu": emp.coin+=50000; t="Thưởng 50k Xu"
        db.commit(); await update.message.reply_text(f"✅ {t} cho {emp.name}")
    db.close()

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID: return
    msg = " ".join(context.args)
    db = SessionLocal(); emps = db.query(Employee).all(); db.close()
    for e in emps: 
        try: await context.bot.send_message(e.telegram_id, f"📢 <b>TB:</b>\n{msg}", parse_mode="HTML")
        except: pass
    await update.message.reply_text("Đã gửi.")

# --- APP SETUP ---
bot_app = Application.builder().token(TOKEN).build()

# 1. Đăng ký lệnh ORDER đầu tiên (Ưu tiên số 1)
bot_app.add_handler(CommandHandler("order", order_command))

# 2. Các lệnh khác
bot_app.add_handler(CommandHandler("start", start_command))
bot_app.add_handler(CommandHandler("me", me_command))
bot_app.add_handler(CommandHandler("top", top_command))
bot_app.add_handler(CommandHandler("qr", qr_command))
bot_app.add_handler(CommandHandler("game", game_ui_command))
bot_app.add_handler(CommandHandler("tx", game_ui_command))
bot_app.add_handler(CommandHandler("pk", game_ui_command))
bot_app.add_handler(CommandHandler("diemdanh", daily_command))
bot_app.add_handler(CommandHandler("shop", shop_command))
bot_app.add_handler(CommandHandler("admin", admin_dashboard))
bot_app.add_handler(CommandHandler("thong_bao", broadcast))

# 3. Handlers phụ
bot_app.add_handler(CallbackQueryHandler(handle_game_buttons))
bot_app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))
bot_app.add_handler(MessageHandler(filters.Regex(r"^/(tip|fine|tipxu)_"), quick_action))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi động Bot theo chuẩn v21.9
    await bot_app.initialize()
    await bot_app.start()
    
    # Xóa Webhook cũ để tránh lỗi Conflict
    await bot_app.bot.delete_webhook(drop_pending_updates=True)
    
    # Cài menu
    await bot_app.bot.set_my_commands([
        BotCommand("order", "⚡ Mở Menu Order"),
        BotCommand("start", "🏠 Về Menu chính"),
        BotCommand("me", "💳 Ví & Thẻ"),
        BotCommand("game", "🎰 Chơi Game"),
        BotCommand("diemdanh", "📅 Điểm danh"),
        BotCommand("shop", "🛒 Shop quà"),
        BotCommand("qr", "🚀 Lấy mã QR"),
        BotCommand("top", "🏆 BXH"),
    ])
    
    # Chạy Polling
    await bot_app.updater.start_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    print("✅ BOT STARTED SUCCESSFULLY!")
    
    yield
    
    print("🛑 STOPPING BOT...")
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

@app.get("/webapp")
async def webapp(request: Request):
    return templates.TemplateResponse("webapp.html", {"request": request})

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
