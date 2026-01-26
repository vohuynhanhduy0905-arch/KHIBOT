# --- FILE: config.py ---
# Cấu hình tập trung cho toàn bộ ứng dụng

import os

# === TELEGRAM ===
TOKEN = os.environ.get("TELEGRAM_TOKEN")
ADMIN_ID = "1587932557"
MAIN_GROUP_ID = -1003566594243
ORDER_TOPIC_ID = 180
GAME_TOPIC_ID = 181
CHAT_TOPIC_ID = 3
GROUP_INVITE_LINK = "https://t.me/c/3566594243/2"

# === WEB ===
WEB_URL = "https://trasuakhi.onrender.com"
MAPS_URL = "https://www.google.com/maps/place/KH%E1%BB%88+MILKTEA+%26+MACCHIATO/@9.5996676,105.9736035,17z/data=!4m6!3m5!1s0x31a04df7049cd473:0xc085b8838ce2b39!8m2!3d9.5996676!4d105.9736035!16s%2Fg%2F11jx4pcl6m?hl=vi"

# === REWARD CONFIG ===
DAILY_CHECKIN_REWARD = 10000
STREAK_7_BONUS = 30000
REACT_REWARD = 1000

# Hộp quà may mắn
GIFT_REWARDS = [
    (5000, 50),
    (10000, 30),
    (15000, 15),
    (20000, 5),
]

# === RANK CONFIG ===
RANK_LEVELS = [
    (0, "Dân Thường", "🌱"),
    (10000, "Kẻ Tập Sự", "🪵"),
    (30000, "Người Mới", "🥉"),
    (50000, "Tân Binh", "🥈"),
    (70000, "Kẻ Thách Thức", "⚔️"),
    (100000, "Chiến Binh", "🛡️"),
    (150000, "Cao Thủ", "🥋"),
    (200000, "Đại Gia", "💎"),
    (300000, "Bá Chủ", "👑"),
    (500000, "Huyền Thoại", "👑🐉"),
]

# === EMOJI POOL ===
EMOJI_POOL = [
    "🍇", "🍈", "🍉", "🍊", "🍋", "🍌", "🍍", "🥭", "🍎", "🍏", "🍐", "🍑", "🍒", "🍓", "🥝", "🍅", "🥥", 
    "🥑", "🍆", "🥔", "🥕", "🌽", "🌶️", "🥒", "🥬", "🥦", "🧄", "🧅", "🍄", "🥜", "🌰", "🍞", "🥐", "🥖", 
    "🥨", "🥯", "🥞", "🧇", "🧀", "🍖", "🍗", "🥩", "🥓", "🍔", "🍟", "🍕", "🌭", "🥪", "🌮", "🌯", "🥙", 
    "🧆", "🥚", "🍳", "🥘", "🍲", "🥣", "🥗", "🍿", "🧈", "🧂", "🥫", "🍱", "🍘", "🍙", "🍚", "🍛", "🍜", 
    "🍝", "🍠", "🍢", "🍣", "🍤", "🍥", "🥮", "🍡", "🥟", "🥠", "🥡", "🦀", "🦞", "🦐", "🦑", "🦪", "🍦", 
    "🍧", "🍨", "🍩", "🍪", "🎂", "🍰", "🧁", "🥧", "🍫", "🍬", "🍭", "🍮", "🍯", "🍼", "🥛", "☕", "🍵", 
    "🍶", "🍾", "🍷", "🍸", "🍹", "🍺", "🍻", "🥂", "🥃", "🥤", "🧃", "🧉", "🧊", "🥢", "🍽️", "🍴", "🥄"
]

# === KÉO BÚA BAO ===
KBB_CHOICES = {
    "kbb_rock": ("✊", "Búa"),
    "kbb_paper": ("✋", "Bao"),
    "kbb_scissors": ("✌️", "Kéo")
}

KBB_RULES = {
    "kbb_rock": "kbb_scissors",
    "kbb_scissors": "kbb_paper",
    "kbb_paper": "kbb_rock"
}

# === THÔNG BÁO TỰ ĐỘNG ===
MORNING_MESSAGES = [
    "☀️ <b>CHÀO BUỔI SÁNG!</b>\n\nChúc cả team ca sáng năng lượng tràn đầy! 💪\n\n❤️ Thả tim để nhận 1,000 Xu!",
    "🌅 <b>NGÀY MỚI AN LÀNH!</b>\n\nCố lên nào các chiến binh KHỈ MILKTEA! 🐒\n\n❤️ Thả tim để nhận 1,000 Xu!",
    "🌞 <b>GOOD MORNING TEAM!</b>\n\nMột ngày tuyệt vời đang chờ đón! ✨\n\n❤️ Thả tim để nhận 1,000 Xu!",
]

EVENING_MESSAGES = [
    "🌆 <b>CHÀO CA CHIỀU!</b>\n\nCố lên team ơi, sắp hết ngày rồi! 💪\n\n❤️ Thả tim để nhận 1,000 Xu!",
    "🌇 <b>BUỔI CHIỀU VUI VẺ!</b>\n\nCảm ơn team đã cố gắng! 🙏\n\n❤️ Thả tim để nhận 1,000 Xu!",
    "☕ <b>BREAK TIME!</b>\n\nNghỉ ngơi chút rồi chiến tiếp nha! 🍵\n\n❤️ Thả tim để nhận 1,000 Xu!",
]
