# --- FILE: utils/helpers.py ---
# Các hàm tiện ích dùng chung

import io
import random
import asyncio
import time
from PIL import Image, ImageDraw, ImageFont
from config import RANK_LEVELS, GIFT_REWARDS

# === SPAM TRACKER ===
SPAM_TRACKER = {}

def get_rank_info(balance: float) -> tuple[str, str]:
    """Lấy tên rank và icon dựa trên balance"""
    name, icon = "Dân Thường", "🌱"
    for threshold, rank_name, rank_icon in RANK_LEVELS:
        if balance >= threshold:
            name, icon = rank_name, rank_icon
    return name, icon


def get_random_gift() -> int:
    """Random phần thưởng hộp quà theo tỉ lệ"""
    total = sum(weight for _, weight in GIFT_REWARDS)
    r = random.randint(1, total)
    cumulative = 0
    for reward, weight in GIFT_REWARDS:
        cumulative += weight
        if r <= cumulative:
            return reward
    return GIFT_REWARDS[0][0]


def crop_to_circle(img: Image.Image) -> Image.Image:
    """Cắt ảnh thành hình tròn"""
    mask = Image.new('L', img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + img.size, fill=255)
    output = Image.new('RGBA', img.size, (0, 0, 0, 0))
    output.paste(img, (0, 0), mask)
    return output


def create_card_image(name: str, emoji: str, balance: float, coin: float, avatar_bytes=None) -> io.BytesIO:
    """Tạo ảnh thẻ nhân viên"""
    W, H = 800, 500
    
    try:
        img = Image.open("static/card_bg.jpg").convert("RGBA")
        img = img.resize((W, H))
    except:
        img = Image.new('RGBA', (W, H), color='#1A5336')

    draw = ImageDraw.Draw(img)

    # Logo
    try:
        logo = Image.open("static/logo.png").convert("RGBA")
        logo_size = 110
        logo = logo.resize((logo_size, logo_size))
        logo = crop_to_circle(logo)
        img.paste(logo, (W - logo_size - 30, 30), logo)
    except: 
        pass

    # Avatar
    if avatar_bytes:
        try:
            avatar = Image.open(avatar_bytes).convert("RGBA")
            avatar = avatar.resize((160, 160))
            avatar = crop_to_circle(avatar)
            draw.ellipse((W//2 - 82, 38, W//2 + 82, 202), outline="#F4D03F", width=3) 
            img.paste(avatar, (W//2 - 80, 40), avatar)
        except: 
            pass

    # Fonts
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
        except:
            text_width = font.getlength(text)
        x = (W - text_width) / 2
        draw.text((x, y), text, font=font, fill=color)

    draw_centered(230, name, font_name, "white")
    draw_centered(300, f"{rank_name}", font_rank, "#F4D03F") 
    draw_centered(350, f"Ví: {balance:,.0f}đ", font_money, "white")
    draw_centered(410, f"Xu: {coin:,.0f}", font_money, "#00FF00")

    bio = io.BytesIO()
    bio.name = 'card.png'
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio


def generate_streak_display(streak: int) -> str:
    """Tạo hiển thị streak (🟢⚪⚪⚪⚪⚪⚪)"""
    current_week_day = streak % 7 if streak % 7 != 0 else 7 if streak > 0 else 0
    display = ""
    for i in range(1, 8):
        if i <= current_week_day:
            display += "🟢"
        else:
            display += "⚪"
    return display
