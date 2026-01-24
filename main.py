import os
import random
import asyncio
import io
import uuid
from datetime import date
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

# --- TELEGRAM IMPORT ---
from telegram import (
    Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, BotCommand, 
    InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, 
    InputTextMessageContent, WebAppInfo, MenuButtonWebApp
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes, 
    CallbackQueryHandler, InlineQueryHandler
)

# --- DATABASE IMPORT ---
# (Giữ nguyên các import này, nhưng mình sẽ viết lại class Employee bên dưới để bạn update db)
from sqlalchemy import create_engine, Column, Integer, String, Date, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from PIL import Image, ImageDraw, ImageFont

# --- CẤU HÌNH ---
TOKEN = os.environ.get("TELEGRAM_TOKEN") 
ADMIN_ID = "1587932557"
WEB_URL = "https://trasuakhi.onrender.com"
MAIN_GROUP_ID = -1003566594243

# --- DATABASE SETUP (Update Model) ---
Base = declarative_base()
class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True)
    name = Column(String)
    emoji = Column(String)
    # TÁCH BIỆT TIỀN:
    salary = Column(Integer, default=0)       # Tiền lương (Maps/Tip) - TIỀN THẬT
    coin = Column(Integer, default=1000)      # Xu game (Điểm danh/Nhiệm vụ) - TIỀN ẢO
    last_checkin = Column(Date, nullable=True) # Ngày điểm danh gần nhất

class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True)
    content = Column(String)

class ReviewLog(Base):
    __tablename__ = "review_logs"
    id = Column(Integer, primary_key=True)
    staff_id = Column(String)
    reviewer_name = Column(String)
    stars = Column(Integer)
    created_at = Column(String)

engine = create_engine("sqlite:///employee.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

# Setup
init_db()
templates = Jinja2Templates(directory="templates")

# List Emoji
EMOJI_POOL = ["🍇", "🍈", "🍉", "🍊", "🍋", "🍌", "🍍", "🥭", "🍎", "🍏", "🍐", "🍑", "🍒", "🍓", "🥝", "🍅", "🥥", "🥑", "🍆", "🥔", "🥕", "🌽", "🌶️", "🥒", "🥬", "🥦"]

# --- HÀM HÌNH ẢNH (Avatar tròn, Thẻ...) ---
def crop_to_circle(img):
    mask = Image.new('L', img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + img.size, fill=255)
    output = Image.new('RGBA', img.size, (0, 0, 0, 0))
    output.paste(img, (0, 0), mask)
    return output

def create_card_image(name, emoji, salary, coin, avatar_bytes=None):
    W, H = 800, 500
    try: img = Image.open("static/card_bg.jpg").convert("RGBA").resize((W, H))
    except: img = Image.new('RGBA', (W, H), color='#1A5336')
    draw = ImageDraw.Draw(img)

    # Logo
    try:
        logo = Image.open("static/logo.png").convert("RGBA").resize((110, 110))
        img.paste(crop_to_circle(logo), (W - 140, 30), crop_to_circle(logo))
    except: pass

    # Avatar
    if avatar_bytes:
        try:
            avatar = Image.open(avatar_bytes).convert("RGBA").resize((160, 160))
            draw.ellipse((W//2 - 82, 38, W//2 + 82, 202), outline="#F4D03F", width=3) 
            img.paste(crop_to_circle(avatar), (W//2 - 80, 40), crop_to_circle(avatar))
        except: pass

    # Text
    try:
        f_name = ImageFont.truetype("static/font.ttf", 65) 
        f_info = ImageFont.truetype("static/font.ttf", 35)
    except:
        f_name = ImageFont.load_default()
        f_info = ImageFont.load_default()

    def draw_centered(y, text, font, color):
        try: w = draw.textlength(text, font=font)
        except: w = font.getlength(text)
        draw.text(((W - w) / 2, y), text, font=font, fill=color)

    draw_centered(230, name, f_name, "white")
    draw_centered(320, f"Lương: {salary:,.0f}đ", f_info, "#F4D03F") # Tiền thật
    draw_centered(380, f"Xu Game: {coin:,.0f} 🪙", f_info, "white") # Tiền ảo
    
    bio = io.BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

# --- LOGIC GAME ---
ACTIVE_PK_MATCHES = {} # Lưu tạm các kèo đang chờ

# 1. KIỂM TRA MÔI TRƯỜNG CHAT (Chặn Group)
async def check_group_spam(update: Update):
    if update.effective_chat.type != "private":
        try: await update.message.delete()
        except: pass
        return True # Là Group
    return False # Là Private

# 2. HỆ THỐNG MENU (Chỉ hiện ở Private)
async def game_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_group_spam(update): return # Chặn nhóm

    user = update.effective_user
    msg = f"🎰 <b>TRUNG TÂM GIẢI TRÍ</b> 🎰\nXin chào <b>{user.full_name}</b>!\nDùng <b>Xu Game (🪙)</b> để chơi nhé."
    kb = [
        [InlineKeyboardButton("📅 Điểm Danh (+Xu)", callback_data="daily_checkin")],
        [
            InlineKeyboardButton("🎲 Tài Xỉu", callback_data="menu_tx"),
            InlineKeyboardButton("🥊 PK Đối Kháng", callback_data="menu_pk")
        ],
        [InlineKeyboardButton("❌ Đóng", callback_data="close_menu")]
    ]
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

# 3. HỆ THỐNG ĐIỂM DANH
async def daily_checkin_logic(user_id, name):
    db = SessionLocal()
    emp = db.query(Employee).filter(Employee.telegram_id == str(user_id)).first()
    
    if not emp: db.close(); return False, "⚠️ Bạn chưa đăng ký! Gõ /start"
    
    today = date.today()
    if emp.last_checkin == today:
        db.close()
        return False, f"📅 Hôm nay {name} điểm danh rồi!\nMai quay lại nhé."
    
    bonus = random.choice([500, 1000, 1500, 2000]) # Random xu
    emp.coin += bonus
    emp.last_checkin = today
    new_bal = emp.coin
    db.commit()
    db.close()
    return True, f"✅ <b>ĐIỂM DANH THÀNH CÔNG!</b>\nBạn nhận được: <b>+{bonus} xu</b> 🪙\n💰 Tổng xu: {new_bal}"

# 4. XỬ LÝ NÚT BẤM
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data
    
    # --- ĐIỂM DANH ---
    if data == "daily_checkin":
        success, msg = await daily_checkin_logic(user.id, user.full_name)
        if success: await query.edit_message_text(msg, parse_mode="HTML")
        else: await query.answer(msg, show_alert=True)
        return

    # --- MENU ĐIỀU HƯỚNG ---
    if data == "close_menu": await query.delete_message(); return
    if data == "back_home": await game_menu_command(update, context); return

    if data == "menu_tx":
        txt = "🎲 <b>TÀI XỈU (Dùng Xu)</b>\n🔴 XỈU (3-10) | 🔵 TÀI (11-18)"
        kb = [[InlineKeyboardButton("🔴 XỈU", callback_data="tx_c_xiu"), InlineKeyboardButton("🔵 TÀI", callback_data="tx_c_tai")], [InlineKeyboardButton("🔙 Menu", callback_data="back_home")]]
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML"); return

    if data == "menu_pk":
        txt = "🥊 <b>PK ĐỐI KHÁNG</b>\nTạo kèo rồi gửi vào nhóm để solo!"
        kb = [[InlineKeyboardButton("⚡ 500 xu", callback_data="pk_new_500"), InlineKeyboardButton("⚡ 1k xu", callback_data="pk_new_1000"), InlineKeyboardButton("⚡ 5k xu", callback_data="pk_new_5000")], [InlineKeyboardButton("🔙 Menu", callback_data="back_home")]]
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML"); return

    # --- GAME TÀI XỈU (Chơi 1 mình) ---
    if data.startswith("tx_c_"):
        choice = "XỈU" if "xiu" in data else "TÀI"
        code = data.split("_")[2]
        kb = [[InlineKeyboardButton("100 xu", callback_data=f"tx_p_{code}_100"), InlineKeyboardButton("500 xu", callback_data=f"tx_p_{code}_500"), InlineKeyboardButton("All-in", callback_data=f"tx_p_{code}_all")], [InlineKeyboardButton("🔙", callback_data="menu_tx")]]
        await query.edit_message_text(f"Bạn chọn: <b>{choice}</b>\nCược bao nhiêu xu?", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML"); return

    if data.startswith("tx_p_"):
        try:
            _, _, code, amt_str = data.split("_")
            db = SessionLocal()
            emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
            if not emp: db.close(); return
            
            amount = emp.coin if amt_str == "all" else int(amt_str)
            if amount <= 0 or emp.coin < amount:
                await query.answer("💸 Không đủ xu!", show_alert=True); db.close(); return

            emp.coin -= amount
            m = await context.bot.send_dice(query.message.chat_id)
            dice = m.dice.value
            await asyncio.sleep(3)
            
            # Logic đơn giản: 1 xúc xắc (1-3 Xỉu, 4-6 Tài) cho nhanh, hoặc bạn muốn 3 viên như cũ?
            # Để nhanh gọn mình để 1 viên nhé. Nếu muốn 3 viên bảo mình sửa.
            is_win = False
            result_txt = "XỈU" if dice <= 3 else "TÀI"
            
            if (code == "xiu" and dice <= 3) or (code == "tai" and dice > 3):
                profit = int(amount * 0.95)
                emp.coin += (amount + profit)
                msg = f"✅ <b>THẮNG!</b> (+{profit} xu)"
            else:
                msg = f"❌ <b>THUA!</b> (-{amount} xu)"
            
            db.commit()
            await query.message.delete() # Xóa menu cũ
            await m.delete() # Xóa xúc xắc
            await context.bot.send_message(query.message.chat_id, f"🎲 Kết quả: {dice} ({result_txt})\n{msg}\n💰 Xu còn: {emp.coin}", parse_mode="HTML")
            db.close()
        except: pass
        return

    # --- GAME PK (TẠO KÈO & CHIA SẺ) ---
    if data.startswith("pk_new_"):
        amount = int(data.split("_")[2])
        db = SessionLocal()
        emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
        
        if not emp or emp.coin < amount:
            await query.answer("💸 Không đủ xu!", show_alert=True); db.close(); return
        
        # Tạo ID kèo
        match_id = str(uuid.uuid4())[:8]
        ACTIVE_PK_MATCHES[match_id] = {
            "creator_id": str(user.id),
            "creator_name": emp.name,
            "amount": amount
        }
        
        # Tạo nút CHIA SẺ (Switch Inline)
        kb = [[InlineKeyboardButton("🚀 Gửi vào nhóm chiến ngay", switch_inline_query=match_id)]]
        await query.edit_message_text(f"✅ Đã tạo kèo <b>{amount} xu</b>.\nBấm nút dưới để gửi lời mời vào nhóm!", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        db.close(); return

    # --- GAME PK (NHẬN KÈO TRONG NHÓM) ---
    if data.startswith("pk_join_"):
        match_id = data.split("_")[2]
        match = ACTIVE_PK_MATCHES.get(match_id)
        chat_id = query.message.chat_id
        
        if not match: await query.answer("❌ Kèo này đã xong hoặc bị hủy!", show_alert=True); return
        if str(user.id) == match["creator_id"]: await query.answer("🚫 Không được tự chơi với mình!", show_alert=True); return
        
        db = SessionLocal()
        p1 = db.query(Employee).filter(Employee.telegram_id == match["creator_id"]).first()
        p2 = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
        amount = match["amount"]
        
        if not p2 or p2.coin < amount: await query.answer("💸 Bạn không đủ xu!", show_alert=True); db.close(); return
        if p1.coin < amount: await query.answer("❌ Chủ kèo đã hết xu!", show_alert=True); db.close(); return

        # Trừ tiền
        p1.coin -= amount; p2.coin -= amount
        db.commit()
        del ACTIVE_PK_MATCHES[match_id] # Xóa kèo

        # Bắt đầu Game trong nhóm
        msg_start = await context.bot.send_message(chat_id, f"🥊 <b>PK BẮT ĐẦU!</b>\n🔴 {p1.name} 🆚 🔵 {p2.name}", parse_mode="HTML")
        
        m1 = await context.bot.send_dice(chat_id) # P1
        d1 = m1.dice.value
        await asyncio.sleep(2)
        m2 = await context.bot.send_dice(chat_id) # P2
        d2 = m2.dice.value
        await asyncio.sleep(3.5)

        # Kết quả
        total = amount * 2
        prize = int(total * 0.95) # Phí 5%
        log_txt = f"🥊 <b>KẾT QUẢ PK ({amount} xu)</b>\n🔴 {p1.name}: {d1}\n🔵 {p2.name}: {d2}\n"
        
        if d1 > d2:
            p1.coin += prize
            log_txt += f"🏆 <b>{p1.name} THẮNG!</b> (+{prize} xu)"
        elif d2 > d1:
            p2.coin += prize
            log_txt += f"🏆 <b>{p2.name} THẮNG!</b> (+{prize} xu)"
        else:
            p1.coin += amount; p2.coin += amount
            log_txt += "🤝 <b>HÒA!</b> (Hoàn tiền)"
        
        db.commit()
        
        # Gửi kết quả riêng cho 2 người
        try: await context.bot.send_message(p1.telegram_id, log_txt + f"\n💰 Xu hiện tại: {p1.coin}", parse_mode="HTML")
        except: pass
        try: await context.bot.send_message(p2.telegram_id, log_txt + f"\n💰 Xu hiện tại: {p2.coin}", parse_mode="HTML")
        except: pass

        # Xóa sạch trong nhóm sau 10s
        await asyncio.sleep(10)
        try:
            await query.message.delete() # Lời mời
            await msg_start.delete()
            await m1.delete()
            await m2.delete()
        except: pass
        db.close()
        return

# 5. XỬ LÝ CHIA SẺ KÈO (INLINE QUERY)
async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query
    if not query: return

    # Nếu query là ID kèo (được gửi từ nút bấm)
    match_id = query.strip()
    if match_id in ACTIVE_PK_MATCHES:
        match = ACTIVE_PK_MATCHES[match_id]
        amount = match["amount"]
        
        results = [
            InlineQueryResultArticle(
                id=match_id,
                title=f"Gửi lời mời PK {amount} xu",
                description="Bấm để gửi vào nhóm",
                input_message_content=InputTextMessageContent(
                    f"🔥 <b>THÁCH ĐẤU PK</b> 🔥\n💰 Cược: <b>{amount} xu</b>\n👇 Ai dám nhận không?",
                    parse_mode="HTML"
                ),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🥊 NHẬN KÈO NGAY", callback_data=f"pk_join_{match_id}")]
                ])
            )
        ]
        await update.inline_query.answer(results, cache_time=0)

# --- COMMANDS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_group_spam(update): return

    user = update.effective_user
    db = SessionLocal()
    emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
    
    if not emp:
        # Tạo NV mới
        emp = Employee(telegram_id=str(user.id), name=user.full_name, emoji="😀", coin=1000, salary=0)
        db.add(emp); db.commit()
    
    # Gửi QR Web App
    url = f"{WEB_URL}/webapp" # Link Web Order
    msg = f"Chào <b>{emp.name}</b>!\nBạn đã được cấp 1000 xu khởi nghiệp."
    
    # Menu Nút WebApp (Cấu hình nút Menu góc trái)
    # Lưu ý: WebApp Button thường cấu hình qua BotFather, nhưng ta có thể gửi kèm message
    kb = ReplyKeyboardMarkup([
        [KeyboardButton(text="🛒 Mở Web Order", web_app=WebAppInfo(url=url))]
    ], resize_keyboard=True)

    await update.message.reply_text(msg, reply_markup=kb, parse_mode="HTML")
    db.close()

async def me_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_group_spam(update): return
    
    user = update.effective_user
    db = SessionLocal()
    emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
    
    if emp:
        # Vẽ ảnh thẻ (Code vẽ ảnh đã update coin/salary)
        photo_io = await asyncio.get_running_loop().run_in_executor(None, create_card_image, emp.name, emp.emoji, emp.salary, emp.coin, None)
        await update.message.reply_photo(photo_io, caption="💳 Thẻ của bạn đây!", parse_mode="HTML")
    else:
        await update.message.reply_text("Chưa đăng ký!")
    db.close()

async def thong_bao_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID: return
    msg = " ".join(context.args)
    if msg:
        db = SessionLocal(); emps = db.query(Employee).all()
        for e in emps: 
            try: await context.bot.send_message(e.telegram_id, f"📢 <b>THÔNG BÁO:</b>\n{msg}", parse_mode="HTML")
            except: pass
        await update.message.reply_text("✅ Đã gửi.")
        db.close()

# --- FASTAPI & LIFESPAN ---
bot_app = Application.builder().token(TOKEN).build()
bot_app.add_handler(CommandHandler("start", start_command))
bot_app.add_handler(CommandHandler("me", me_command))
bot_app.add_handler(CommandHandler("game", game_menu_command))
bot_app.add_handler(CommandHandler("diemdanh", lambda u,c: daily_checkin_logic(u.effective_user.id, u.effective_user.full_name))) # Lối tắt
bot_app.add_handler(CommandHandler("thong_bao", thong_bao_command))
bot_app.add_handler(CallbackQueryHandler(handle_buttons))
bot_app.add_handler(InlineQueryHandler(inline_query_handler)) # Handler chia sẻ PK

@asynccontextmanager
async def lifespan(app: FastAPI):
    await bot_app.initialize()
    await bot_app.start()
    
    # Cấu hình Menu Button WebApp mặc định cho toàn bộ user
    await bot_app.bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(text="🛒 Order Nhanh", web_app=WebAppInfo(url=f"{WEB_URL}/webapp"))
    )
    
    asyncio.create_task(bot_app.updater.start_polling())
    print("✅ Bot Started & DB Updated!")
    yield
    await bot_app.updater.stop()
    await bot_app.stop()
    await bot_app.shutdown()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.head("/ping")
@app.get("/ping")
def ping(): return {"status": "ok"}

@app.get("/webapp", response_class=HTMLResponse)
async def webapp(request: Request):
    return templates.TemplateResponse("webapp.html", {"request": request})

# API nhận đơn từ WebApp (Giữ nguyên hoặc update xử lý lương nếu cần)
@app.post("/api/order")
async def receive_order(request: Request):
    data = await request.json()
    # Logic xử lý đơn hàng, cộng salary cho nhân viên nếu cần
    # ...
    return {"status": "success"}
    
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








