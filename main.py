import os
import random
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from database import SessionLocal, Employee, ReviewLog, Review, init_db
from sqlalchemy import desc

# --- CẤU HÌNH ---
TOKEN = "7689995852:AAGyc6U2X65C1ojPIeedFepdiOK97vEPtFE"
ADMIN_ID = "1587932557"
WEB_URL = "https://micayitadasoctrang.onrender.com" 

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
        logs = db.query(ReviewLog).filter(ReviewLog.staff_id == user_id).order_by(desc(ReviewLog.created_at)).limit(5).all()
        history = "\n".join([f"- {l.stars}⭐: {l.reviewer_name}" for l in logs]) if logs else "Chưa có review nào."
        await update.message.reply_text(f"💰 Ví: {emp.balance:,.0f}đ\nIcon: {emp.emoji}\n\n🕒 Lịch sử:\n{history}")
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

# --- 2. ADMIN SYSTEM ---

# Hàm xử lý logic lệnh (để tái sử dụng)
async def view_review_logic(update, context):
    db = SessionLocal()
    reviews = db.query(Review).all()
    if not reviews:
        await update.message.reply_text("Kho review đang TRỐNG.")
    else:
        msg = "📝 <b>KHO REVIEW HIỆN TẠI:</b>\n\n"
        for r in reviews:
            msg += f"- {r.content}\n"
        if len(msg) > 4000: await update.message.reply_text(msg[:4000] + "...", parse_mode="HTML")
        else: await update.message.reply_text(msg, parse_mode="HTML")
    db.close()

async def reset_review_logic(update, context):
    db = SessionLocal()
    try:
        num = db.query(Review).delete()
        db.commit()
        await update.message.reply_text(f"🗑 Đã xóa sạch {num} câu review rác.\nGiờ hãy chat nội dung mới để nạp lại.")
    except: await update.message.reply_text("Lỗi xóa DB.")
    finally: db.close()

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
        await update.message.reply_text(f"✅ Đã thêm {count} câu review vào kho.")
    except: pass
    db.close()

# MENU ADMIN (ĐÃ THÊM NÚT REVIEW)
async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID: return
    keyboard = [
        ["📋 Danh Sách NV", "📢 Gửi Thông Báo"],
        ["📝 Xem Kho Review", "🗑 Xóa Hết Review"],  # <--- ĐÃ THÊM DÒNG NÀY
        ["🔄 Reset Tiền NV", "❌ Thoát Admin"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("🔓 <b>MENU ADMIN</b>", reply_markup=reply_markup, parse_mode="HTML")

# Xử lý bấm nút
async def handle_admin_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text
    
    if user_id != ADMIN_ID: 
        valid_buttons = ["📋 Danh Sách NV", "📢 Gửi Thông Báo", "🔄 Reset Tiền NV", "❌ Thoát Admin", "📝 Xem Kho Review", "🗑 Xóa Hết Review"]
        if text not in valid_buttons:
            await handle_add_review(update, context)
        return

    db = SessionLocal()
    
    if text == "📋 Danh Sách NV":
        emps = db.query(Employee).all()
        if not emps:
            await update.message.reply_text("Chưa có nhân viên.")
        else:
            msg = "📋 <b>QUẢN LÝ NHÂN VIÊN</b>\n(Chạm vào lệnh để thao tác)\n\n"
            for e in emps:
                msg += (
                    f"👤 <b>{e.name}</b> ({e.emoji}) | 💰 {e.balance:,.0f}đ\n"
                    f"👉 /tip_{e.telegram_id} (Thưởng 5k)\n"
                    f"👉 /fine_{e.telegram_id} (Phạt 5k)\n"
                    f"👉 /del_{e.telegram_id} (Xóa NV)\n"
                    f"------------------\n"
                )
            await update.message.reply_text(msg, parse_mode="HTML")

    elif text == "📝 Xem Kho Review":
        await view_review_logic(update, context)

    elif text == "🗑 Xóa Hết Review":
        await reset_review_logic(update, context)

    elif text == "🔄 Reset Tiền NV":
        db.query(Employee).update({Employee.balance: 0})
        db.commit()
        await update.message.reply_text("✅ Đã reset toàn bộ ví về 0.")

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
    if not emp:
        await update.message.reply_text("❌ Không tìm thấy NV.")
        db.close(); return

    if action == "tip":
        emp.balance += 5000 
        await update.message.reply_text(f"✅ Thưởng 5k cho {emp.name}.") 
        try: await context.bot.send_message(target_id, "🎁 Sếp thưởng nóng 5k!")
        except: pass
    elif action == "fine":
        emp.balance -= 5000 
        await update.message.reply_text(f"✅ Phạt 5k {emp.name}.")
    elif action == "del":
        name = emp.name
        db.delete(emp)
        await update.message.reply_text(f"🗑 Đã xóa {name}.")
    db.commit(); db.close()

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID: return
    msg = " ".join(context.args)
    if not msg: return
    db = SessionLocal()
    emps = db.query(Employee).all()
    count = 0
    for e in emps:
        try:
            await context.bot.send_message(e.telegram_id, f"📢 <b>THÔNG BÁO:</b>\n{msg}", parse_mode="HTML")
            count += 1
        except: pass
    await update.message.reply_text(f"✅ Đã gửi {count} người.")
    db.close()

# Lệnh Slash commands (Dùng song song với nút bấm)
async def view_review_command(update, context): await view_review_logic(update, context)
async def reset_review_command(update, context): await reset_review_logic(update, context)

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
    maps_url = "https://www.google.com/maps/place/Mi+Cay+ITADA+S%C3%93C+TR%C4%82NG/@9.607104,105.9731197,17z/data=!3m1!4b1!4m6!3m5!1s0x31a04d006ab38ec5:0x66fa8e46b9e1fce8!8m2!3d9.607104!4d105.9756946!16s%2Fg%2F11vrx94rp4?hl=vi"
    return templates.TemplateResponse("index.html", {"request": request, "maps_url": maps_url, "staff_emoji": emoji})

@app.get("/api/get_review")
def get_review():
    db = SessionLocal()
    review = db.query(Review).order_by(func.random()).first()
    db.close()
    
    if review:
        content = review.content
    else:
        # 2. Nếu DB trống thì mới dùng mẫu dự phòng này
        backup_samples = [
            "Mì cay nước dùng đậm đà, rất vừa miệng. Nhân viên luôn mỉm cười và chào đón khách rất nồng nhiệt, tạo cảm giác được tôn trọng.",
            "Nhân viên phục vụ nhanh nhẹn, dễ thương. Mì cay hải sản ở đây là chân ái, mực với tôm tươi rói luôn, ăn đã cái nư.",
            "Không gian quán thoáng mát, sạch sẽ. Mì cay ITADA quá tuyệt vời, từ món ăn đến con người đều rất dễ thương.",
            "Đồ ăn ra nhanh, nóng hổi. Quán có chỗ để xe rộng rãi, bảo vệ nhiệt tình, vào quán ăn cảm thấy rất an tâm.",
            "Giá cả hợp lý, sẽ quay lại ủng hộ, địa điểm ăn uống số 1 trong lòng mình. Mọi thứ hoàn hảo!"
        ]
        content = random.choice(backup_samples)
        
    return {"content": content}




