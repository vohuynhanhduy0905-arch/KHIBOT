import os
import random
import asyncio
import io
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

# Hàm phụ để cắt ảnh thành hình tròn
def crop_to_circle(img):
    mask = Image.new('L', img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + img.size, fill=255)
    output = Image.new('RGBA', img.size, (0, 0, 0, 0))
    output.paste(img, (0, 0), mask)
    return output
    
# --- COPY ĐOẠN NÀY ĐÈ VÀO HÀM create_card_image CŨ ---
def create_card_image(name, emoji, balance, avatar_bytes=None):
    W, H = 800, 500
    
    # 1. Tạo nền
    try:
        img = Image.open("static/card_bg.jpg").convert("RGBA")
        img = img.resize((W, H))
    except:
        img = Image.new('RGBA', (W, H), color='#F37021')

    draw = ImageDraw.Draw(img)

    # 2. Xử lý Avatar
    if avatar_bytes:
        try:
            avatar = Image.open(avatar_bytes).convert("RGBA")
            avatar = avatar.resize((160, 160))
            avatar = crop_to_circle(avatar)
            img.paste(avatar, (W//2 - 80, 40), avatar)
        except Exception as e:
            print(f"Lỗi avatar: {e}")
            draw.ellipse((W//2 - 80, 40, W//2 + 80, 200), outline="white", width=5)

    # 3. Load Font
    try:
        font_name = ImageFont.truetype("static/font.ttf", 60)
        font_rank = ImageFont.truetype("static/font.ttf", 35)
        font_money = ImageFont.truetype("static/font.ttf", 55)
    except:
        font_name = ImageFont.load_default()
        font_rank = ImageFont.load_default()
        font_money = ImageFont.load_default()

    # 4. Tính Rank (ĐÃ SỬA LỖI THỤT ĐẦU DÒNG Ở ĐÂY)
    rank = "Kẻ Vô Danh"
    if balance >= 10000: rank = "Kẻ Tập Sự"
    if balance >= 30000: rank = "Người Thử Thách"
    if balance >= 50000: rank = "Kẻ Chiến Đấu"
    if balance >= 70000: rank = "Chiến Tướng"
    if balance >= 100000: rank = "Thủ Lĩnh"
    if balance >= 150000: rank = "Thống Soái"
    if balance >= 200000: rank = "Vương"
    if balance >= 300000: rank = "Đế Vương"
    if balance >= 500000: rank = "Chí Tôn"

    # 5. Hàm căn giữa text
    def draw_centered(y, text, font, color):
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
        except:
            text_width = font.getlength(text)
        x = (W - text_width) / 2
        draw.text((x, y), text, font=font, fill=color)

    # 6. Viết chữ
    draw_centered(230, name, font_name, "white")
    draw_centered(310, f"Rank: {rank}", font_rank, "#FFD700") 
    draw_centered(370, f"Ví: {balance:,.0f}đ", font_money, "white")

    # 7. Xuất ảnh
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
    user = update.effective_user
    db = SessionLocal()
    emp = db.query(Employee).filter(Employee.telegram_id == str(user.id)).first()
    
    if emp:
        msg = await update.message.reply_text("📸 Đang lấy ảnh đại diện để in thẻ...")
        
        # --- LOGIC LẤY AVATAR ---
        avatar_io = None
        try:
            # Lấy danh sách ảnh đại diện
            photos = await user.get_profile_photos(limit=1)
            if photos.total_count > 0:
                # Lấy ảnh kích thước lớn nhất (cái cuối cùng trong list)
                photo_file = await photos.photos[0][-1].get_file()
                # Tải ảnh về bộ nhớ đệm
                avatar_bytes = await photo_file.download_as_bytearray()
                avatar_io = io.BytesIO(avatar_bytes)
        except Exception as e:
            print(f"Không lấy được avatar: {e}")
        # ------------------------

        # Gọi hàm vẽ ảnh (truyền avatar vào)
        loop = asyncio.get_running_loop()
        photo_file = await loop.run_in_executor(None, create_card_image, emp.name, emp.emoji, emp.balance, avatar_io)

        # Lấy lịch sử
        logs = db.query(ReviewLog).filter(ReviewLog.staff_id == str(user.id)).order_by(desc(ReviewLog.created_at)).limit(3).all()
        history = "\n".join([f"✅ {l.stars}⭐: {l.reviewer_name}" for l in logs]) if logs else "Chưa có review nào."
        
        caption = f"💳 **THẺ NHÂN VIÊN VIP**\n\n🕒 <b>Lịch sử:</b>\n{history}"

        await update.message.reply_photo(photo=photo_file, caption=caption, parse_mode="HTML")
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg.message_id)
        
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


















