import os
import random
import asyncio
import io
from pilmoji import Pilmoji  
from pilmoji.source import GoogleEmojiSource 
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from database import SessionLocal, Employee, ReviewLog, Review, init_db
from sqlalchemy import desc
from sqlalchemy.sql import func  
from PIL import Image, ImageDraw, ImageFont

# --- CẤU HÌNH ---
TOKEN = os.environ.get("TELEGRAM_TOKEN") 
ADMIN_ID = "1587932557"
WEB_URL = "https://trasuakhi.onrender.com" 

# Setup
init_db()
templates = Jinja2Templates(directory="templates")

# List Emoji
EMOJI_POOL = [
    "🍇", "🍈", "🍉", "🍊", "🍋", "🍌", "🍍", "🥭", "🍎", "🍏", "🍐", "🍑", "🍒", "🍓", "🥝", "🍅", "🥥", 
    "🥑", "🍆", "🥔", "🥕", "🌽", "🌶️", "🥒", "🥬", "🥦", "🧄", "🧅", "🍄", "🥜", "🌰", "🍞", "🥐", "🥖", 
    "🥨", "🥯", "🥞", "🧇", "🧀", "🍖", "🍗", "🥩", "🥓", "🍔", "🍟", "🍕", "🌭", "🥪", "🌮", "🌯", "🥙", 
    "🧆", "🥚", "🍳", "🥘", "🍲", "🥣", "🥗", "🍿", "🧈", "🧂", "🥫", "🍱", "🍘", "🍙", "🍚", "🍛", "🍜", 
    "🍝", "🍠", "🍢", "🍣", "🍤", "🍥", "🥮", "🍡", "🥟", "🥠", "🥡", "🦀", "🦞", "🦐", "🦑", "🦪", "🍦", 
    "🍧", "🍨", "🍩", "🍪", "🎂", "🍰", "🧁", "🥧", "🍫", "🍬", "🍭", "🍮", "🍯", "🍼", "🥛", "☕", "🍵", 
    "🍶", "🍾", "🍷", "🍸", "🍹", "🍺", "🍻", "🥂", "🥃", "🥤", "🧃", "🧉", "🧊", "🥢", "🍽️", "🍴", "🥄"
]

# --- HÀM VẼ THẺ SỬ DỤNG PILMOJI (CÓ MÀU) ---
def create_card_image(name, emoji, balance):
    W, H = 800, 500
    
    # 1. Tạo nền (như cũ)
    try:
        img = Image.open("static/card_bg.jpg").convert("RGBA")
        img = img.resize((W, H))
    except:
        img = Image.new('RGBA', (W, H), color='#F37021')

    # 2. Load Font chữ (Vẫn dùng Roboto cho chữ)
    try:
        # Bạn nhớ tải file Roboto-Bold.ttf đổi tên thành font.ttf bỏ vào static nhé
        font_emoji = ImageFont.truetype("static/font.ttf", 100) 
        font_name = ImageFont.truetype("static/font.ttf", 70)   
        font_rank = ImageFont.truetype("static/font.ttf", 40)   
        font_money = ImageFont.truetype("static/font.ttf", 60)
    except:
        font_emoji = ImageFont.load_default()
        font_name = ImageFont.load_default()
        font_rank = ImageFont.load_default()
        font_money = ImageFont.load_default()

    # 3. Tính toán Rank
    rank = "Tập Sự"
    if balance >= 50000: rank = "Chiến Binh"
    if balance >= 250000: rank = "Đại Gia"
    if balance >= 350000: rank = "Huyền Thoại"

    # 4. Sử dụng Pilmoji để vẽ (Hỗ trợ Emoji màu)
    with Pilmoji(img) as pilmoji:
        # Hàm căn giữa custom cho Pilmoji
        def draw_centered(y, text, font, color):
            # Lấy kích thước text
            try:
                # Pillow mới
                draw = ImageDraw.Draw(img)
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
            except:
                # Pillow cũ
                text_width = font.getlength(text)
                
            x = (W - text_width) / 2
            
            # VẼ BẰNG PILMOJI THAY VÌ DRAW.TEXT
            pilmoji.text((x, y), text, font=font, fill=color, emoji_position_offset=(0, 10))

        # Vẽ nội dung
        draw_centered(50, emoji, font_emoji, "white")        # Emoji sẽ có màu!
        draw_centered(180, name, font_name, "white")
        draw_centered(280, f"Rank: {rank}", font_rank, "#FFD700")
        draw_centered(350, f"Ví: {balance:,.0f}đ", font_money, "white")

    # 5. Xuất ảnh
    bio = io.BytesIO()
    bio.name = 'card.png'
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio
    
# --- 1. LỆNH CƠ BẢN ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = SessionLocal()
    emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
    
    if not emp:
        used_emojis = [e.emoji for e in db.query(Employee).all()]
        available = [e for e in EMOJI_POOL if e not in used_emojis]
        if not available:
            await update.message.reply_text("Hết icon định danh! Liên hệ chủ quán.")
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
    user_id = str(update.effective_user.id)
    db = SessionLocal()
    emp = db.query(Employee).filter(Employee.telegram_id == user_id).first()
    
    if emp:
        # 1. Gửi thông báo "Đang in thẻ..." để user đỡ sốt ruột
        temp_msg = await update.message.reply_text("🎨 Đang thiết kế thẻ VIP của bạn...")
        
        # 2. Gọi hàm vẽ ảnh
        # Chạy trong thread khác để không lag bot nếu vẽ lâu
        loop = asyncio.get_running_loop()
        photo_file = await loop.run_in_executor(None, create_card_image, emp.name, emp.emoji, emp.balance)

        # 3. Lấy lịch sử review để ghi vào caption
        logs = db.query(ReviewLog).filter(ReviewLog.staff_id == user_id).order_by(desc(ReviewLog.created_at)).limit(3).all()
        history_text = "\n".join([f"✅ {l.stars}⭐: {l.reviewer_name}" for l in logs]) if logs else "Chưa có review nào."
        
        caption = f"💳 **THẺ NHÂN VIÊN ITADA**\n\n🕒 <b>Lịch sử gần đây:</b>\n{history_text}\n\n👉 <i>Quét mã QR để tích điểm!</i>"

        # 4. Gửi ảnh và xóa tin nhắn chờ
        await update.message.reply_photo(photo=photo_file, caption=caption, parse_mode="HTML")
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=temp_msg.message_id)
        
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

# Hàm nạp review (Tách riêng để gọi lại)
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

# --- HÀM XỬ LÝ TEXT (SỬA LỖI Ở ĐÂY) ---
async def handle_admin_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text
    
    # Nếu không phải Admin -> Bỏ qua
    if user_id != ADMIN_ID: return

    # Danh sách các nút bấm
    admin_buttons = ["📋 Danh Sách NV", "📢 Gửi Thông Báo", "🔄 Reset Toàn Bộ", "❌ Thoát Admin", "📝 Xem Kho Review", "🗑 Xóa Hết Review"]

    # NẾU KHÔNG PHẢI NÚT BẤM -> THÌ LÀ NẠP REVIEW
    if text not in admin_buttons:
        await handle_add_review(update, context)
        return

    # Nếu là nút bấm -> Xử lý
    db = SessionLocal()
    
    if text == "📋 Danh Sách NV":
        emps = db.query(Employee).all()
        if not emps: await update.message.reply_text("Chưa có nhân viên.")
        else:
            msg = "📋 <b>QUẢN LÝ NHÂN VIÊN</b>\n\n"
            for e in emps:
                msg += (f"👤 <b>{e.name}</b> ({e.emoji}) | {e.balance:,.0f}đ\n👉 /tip_{e.telegram_id} (Thưởng 5k)\n👉 /fine_{e.telegram_id} (Phạt 5k)\n👉 /del_{e.telegram_id} (Xóa)\n---\n")
            await update.message.reply_text(msg, parse_mode="HTML")

    elif text == "📝 Xem Kho Review":
        reviews = db.query(Review).all()
        if not reviews: await update.message.reply_text("Kho review trống.")
        else:
            msg = "📝 <b>REVIEW:</b>\n" + "\n".join([f"- {r.content}" for r in reviews])
            if len(msg)>4000: msg=msg[:4000]+"..."
            await update.message.reply_text(msg)

    elif text == "🗑 Xóa Hết Review":
        db.query(Review).delete(); db.commit()
        await update.message.reply_text("🗑 Đã xóa sạch kho review.")

    elif text == "🔄 Reset Toàn Bộ":
        db.query(Employee).update({Employee.balance: 0}); db.commit()
        await update.message.reply_text("✅ Đã reset ví về 0.")

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
    if not emp: await update.message.reply_text("❌ Lỗi ID."); db.close(); return

    if action == "tip":
        emp.balance += 5000; await update.message.reply_text(f"✅ Thưởng 5k cho {emp.name}.") 
        try: await context.bot.send_message(target_id, "🎁 Sếp thưởng nóng 5k!")
        except: pass
    elif action == "fine":
        emp.balance -= 5000; await update.message.reply_text(f"✅ Phạt 5k {emp.name}.")
    elif action == "del":
        db.delete(emp); await update.message.reply_text(f"🗑 Đã xóa.")
    db.commit(); db.close()

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID: return
    msg = " ".join(context.args)
    if not msg: return
    db = SessionLocal()
    emps = db.query(Employee).all()
    count = 0
    for e in emps:
        try: await context.bot.send_message(e.telegram_id, f"📢 <b>THÔNG BÁO:</b>\n{msg}", parse_mode="HTML"); count += 1
        except: pass
    await update.message.reply_text(f"✅ Đã gửi {count} người."); db.close()

async def view_review_command(update, context): await handle_admin_logic(update, context) # Tái sử dụng logic
async def reset_review_command(update, context): await handle_admin_logic(update, context)


# --- 3. SETUP & STARTUP ---
bot_app = Application.builder().token(TOKEN).build()

bot_app.add_handler(CommandHandler("start", start_command))
bot_app.add_handler(CommandHandler("me", me_command))
bot_app.add_handler(CommandHandler("top", top_command))
bot_app.add_handler(CommandHandler("admin", admin_dashboard))
bot_app.add_handler(CommandHandler("thong_bao", broadcast_command))
bot_app.add_handler(CommandHandler("view_review", view_review_command))
bot_app.add_handler(CommandHandler("reset_review", reset_review_command))
bot_app.add_handler(MessageHandler(filters.Regex(r"^/(tip|fine|del)_"), quick_action_handler))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_logic))

@asynccontextmanager
async def lifespan(app: FastAPI):
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling()
    yield
    await bot_app.updater.stop()
    await bot_app.stop()
    await bot_app.shutdown()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

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

# Cho phép cả GET (trình duyệt) và HEAD (UptimeRobot Free)
@app.head("/ping")
@app.get("/ping")
def ping():
    return {"status": "ok", "message": "Bot is alive!"}

@app.get("/api/get_review")
def get_review():
    db = SessionLocal()
    review = db.query(Review).order_by(func.random()).first()
    db.close()
    
    if review:
        content = review.content
    else:
        # --- SỬA CÁC CÂU MẪU Ở ĐÂY ---
        backup = [
            "Trà sữa thơm béo, topping siêu nhiều luôn. Trà sữa ở đây rẻ mà chất lượng cực, full topping 25k quá hời cho sinh viên.",
            "Quán decor xinh, nước ngon, nhân viên dễ thương. Quán Khỉ gần trường nên mình ghé suốt, trà sữa ô long thơm lắm.",
            "Trà trái cây tươi mát, uống là nghiền. Menu đa dạng quá trời, uống cả tháng không hết món, nhân viên tư vấn rất kỹ.",
            "Sẽ quay lại dài dài, 10 điểm chất lượng. Trà trái cây nhiệt đới uống một lần là ghiền luôn, topping trái cây tươi rói.",
            "Menu đa dạng, giá học sinh, rất ưng ý. Mê nhất trà dâu tằm bên này, thanh mát mà giá lại hạt dẻ."
        ]
        content = random.choice(backup)
        
    return {"content": content}
















