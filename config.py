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

# ==========================================
# === CẤU HÌNH TÀI XỈU (MỚI) ===
# ==========================================
TX_WIN_RATE = 0.80          # Tỷ lệ ăn: 1 ăn 0.80 (giảm từ 0.85)
TX_MAX_PLAYS_PER_DAY = 15   # Tối đa 15 lần chơi/ngày
TX_MAX_BET_PER_DAY = 100000 # Tối đa cược 100,000 Xu/ngày

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
    "☀️ <b>CHÀO BUỔI SÁNG CA SÁNG!</b>\n\nChúc toàn thể nhân sự ca sáng bắt đầu ngày mới với sự tập trung và năng lượng cao nhất. Hãy chuẩn bị mọi thứ thật chỉn chu.\n\n",

    "🌅 <b>KHỞI ĐẦU NGÀY MỚI TẠI KHỈ MILKTEA.</b>\n\nChúc team ca sáng làm việc hiệu quả, phối hợp nhịp nhàng để mang lại trải nghiệm tốt nhất cho khách hàng.\n\n",

    "🌞 <b>THÔNG BÁO CA SÁNG.</b>\n\nChúc các bạn một ca làm việc thuận lợi. Hãy duy trì tiêu chuẩn chất lượng và vệ sinh cửa hàng lên hàng đầu.\n\n",

    "⚡ <b>TINH THẦN KHỈ MILKTEA.</b>\n\nNghiêm túc trong công việc và nhiệt huyết trong phục vụ. Chúc team ca sáng hoàn thành tốt nhiệm vụ được giao.\n\n",

    "🍃 <b>CHÀO NGÀY MỚI NĂNG ĐỘNG.</b>\n\nMọi sự chuẩn bị tốt vào buổi sáng sẽ mang lại kết quả tốt cho cả ngày. Cố lên nhé team ca sáng!\n\n",

    "📋 <b>TRIỂN KHAI CÔNG VIỆC CA SÁNG.</b>\n\nChúc cả team một ngày làm việc chuyên nghiệp, xử lý đơn hàng nhanh chóng và chính xác.\n\n",

    "💎 <b>CAM KẾT CHẤT LƯỢNG.</b>\n\nBắt đầu ngày mới bằng sự tận tâm. Chúc các chiến binh Khỉ Milktea ca sáng gặt hái được nhiều thành công.\n\n"
]

EVENING_MESSAGES = [
    "🌇 <b>BẮT ĐẦU CA CHIỀU.</b>\n\nChúc toàn đội ngũ ca chiều giữ vững phong độ, làm việc tập trung để hoàn thành chỉ tiêu trong ngày.\n\n",

    "🌆 <b>CHÀO TEAM CA CHIỀU.</b>\n\nDù cuối ngày có thể mệt mỏi, hãy cùng nhau duy trì sự chuyên nghiệp đến những đơn hàng cuối cùng.\n\n",

    "🚀 <b>TẬP TRUNG CA CAO ĐIỂM.</b>\n\nCa chiều là thời điểm quan trọng, chúc team phối hợp ăn ý và xử lý công việc thật hiệu quả.\n\n",

    "🤝 <b>TINH THẦN ĐỒNG ĐỘI.</b>\n\nCảm ơn nỗ lực của các bạn trong ca chiều. Hãy hỗ trợ nhau để đảm bảo vận hành tốt nhất tại Khỉ Milktea.\n\n",

    "🌙 <b>NỖ LỰC VỀ ĐÍCH.</b>\n\nChúc team ca chiều có một buổi làm việc năng suất. Sự tỉ mỉ của các bạn chính là bộ mặt của thương hiệu.\n\n",

    "🎯 <b>MỤC TIÊU CA CHIỀU.</b>\n\nHãy đảm bảo mọi quy trình được thực hiện chuẩn xác. Chúc cả team có một ca làm việc thuận lợi và an lành.\n\n",

    "✨ <b>HOÀN THÀNH NHIỆM VỤ.</b>\n\nChúc các bạn ca chiều làm việc đầy nhiệt huyết, giữ vững uy tín chất lượng của Khỉ Milktea cho đến khi đóng cửa.\n\n"
]
