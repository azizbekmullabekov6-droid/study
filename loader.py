import os
import sys
from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
import pytz

# .env faylni yuklaymiz
load_dotenv()

# Tokenni tekshiramiz
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Agar token bo'lmasa, xabar berib to'xtatamiz
if not BOT_TOKEN:
    print("❌ XATOLIK: .env faylida BOT_TOKEN topilmadi!")
    sys.exit(1)

# Admin ID larini olish (xatolik bo'lsa bo'sh ro'yxat qaytaradi)
admin_env = os.getenv("ADMIN_IDS")
if admin_env:
    ADMIN_IDS = [int(x) for x in str(admin_env).split(",")]
else:
    ADMIN_IDS = []

TIMEZONE = pytz.timezone('Asia/Tashkent')
DB_NAME = "study_bot.db"

# Bot va Dvijoklarni yaratamiz
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone=TIMEZONE)
