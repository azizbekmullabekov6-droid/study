import asyncio
import logging
import sys
import random
from datetime import datetime, timedelta
import pytz
from collections import defaultdict
import html 

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove, BotCommand
from aiogram.fsm.storage.memory import MemoryStorage
import aiosqlite
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ==========================================
# ⚙️ SOZLAMALAR
# ==========================================
BOT_TOKEN = "TOKEN_OCHIRILDI"  # <--- ⚠️ TOKENNI O'ZINGIZNIKIGA ALMASHTIRING!
ADMIN_IDS = []           

TIMEZONE = pytz.timezone('Asia/Tashkent')
DB_NAME = "study_bot.db"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler(timezone=TIMEZONE)

# ==========================================
# 🗄 MA'LUMOTLAR BAZASI
# ==========================================
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS activity (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, seconds INTEGER, session_date DATE, timestamp DATETIME)")
        await db.commit()

async def add_user(user: types.User):
    if not user: return
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)", (user.id, user.username, user.full_name))
        await db.commit()

async def log_activity(user_id: int, seconds: int):
    now = datetime.now(TIMEZONE)
    today = now.date()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO activity (user_id, seconds, session_date, timestamp) VALUES (?, ?, ?, ?)", (user_id, seconds, today, now))
        await db.commit()

async def get_leaderboard_data(period="weekly"):
    now = datetime.now(TIMEZONE)
    if period == "today":
        sql_filter = "session_date = ?"
        params = (now.date(),)
    elif period == "weekly":
        start_date = (now - timedelta(days=7)).date()
        sql_filter = "session_date >= ?"
        params = (start_date,)
    elif period == "monthly":
        sql_filter = "strftime('%Y-%m', session_date) = ?"
        params = (now.strftime('%Y-%m'),)
    else: return []

    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(f"SELECT u.username, u.full_name, SUM(a.seconds) as total_seconds FROM activity a JOIN users u ON a.user_id = u.user_id WHERE {sql_filter} GROUP BY a.user_id ORDER BY total_seconds DESC LIMIT 50", params)
        return await cursor.fetchall()

# ==========================================
# 🧠 MANTIQ
# ==========================================
class SessionManager:
    def __init__(self):
        self.status = "IDLE"
        self.active_participants = {}
        self.session_chat_id = None
        self.queue = []
        self.current_job = None
    
    def clear(self):
        self.status = "IDLE"
        self.active_participants.clear()
        self.queue = []
        if self.current_job: self.current_job.remove(); self.current_job = None

session = SessionManager()

def format_time(seconds):
    h, m = divmod(seconds, 3600)
    m, _ = divmod(m, 60)
    return f"{h}h {m}m" if h > 0 else f"{m}m"

# --- 🔥 YANGILANGAN 45+ UNVONLAR RO'YXATI ---
def get_random_title():
    titles = [
        "The GOAT 🐐", "Titan of Focus 🗿", "Grandmaster 🥋", "Legendary Mind 🧠",
        "Time Lord ⏳", "Cyber Monk 🧘‍♂️", "Elite Achiever 💎", "Relentless Machine 🤖",
        "Scholar 📜", "Sharp Shooter 🏹", "Deep Thinker 🌌", "Bookworm 🐛",
        "Courageous Focus 🛡", "Rising Star 🌟", "Knowledge Hunter 🦅", "Consistent Pro 🏗",
        "Mental Athlete 🏋️‍♂️", "Focus Ninja 🥷", "Brain Builder 🧱", "Samurai of Discipline ⚔️", 
        "Angel of Focus 🪽", "Graceful Grinder 🌸", "Precision Crafter 🪛", 
        "Target Locked 🎯", "Night Owl Power 🌛", "Clarity Crafter ✨",
        "Wisdom Keeper 🦉", "Atomic Habit ⚛️", "Limitless 🚀", "Silent Warrior 🗡",
        "Data Cruncher 💻", "Mastermind 🎩", "Future CEO 💼", "Task Slayer 🐉",
        "Flow State Surfer 🏄‍♂️", "Dopamine Detoxer 🥗", "Neural Knight ♟",
        "Exam Crusher 🥊", "1% Club 🥂", "Mindset Mogul 🦁", "Zen Master 🎋",
        "Productivity King 👑", "Speed Learner ⚡️", "Iron Mind 🦾", "Galaxy Brain 🪐"
    ]
    return random.choice(titles)

def clean_name(name):
    if not name: return "Noma'lum"
    return html.escape(name)

# ==========================================
# 🆘 /help
# ==========================================
@dp.message(Command("help"))
@dp.channel_post(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        "🆘 <b>BUYRUQLAR RO'YXATI</b>\n\n"
        "👤 <b>Foydalanuvchilar uchun:</b>\n"
        "• /start — Botni ishga tushirish\n"
        "• /help — Buyruqlar ro'yxatini ko'rish\n\n"
        "👑 <b>Admin (Boshqaruvchi) uchun:</b>\n"
        "• /study25 — 🍅 25 min dars + 5 min tanaffus\n"
        "• /study50 — 🍅 50 min dars + 10 min tanaffus\n"
        "• /study_full — 🔥 25+5 (6 marta - 3 soat)\n"
        "• /study1 — 💀 50+10 (3 marta - Hardcore)\n"
        "• /end_session — 🛑 Sessiyani to'xtatish\n\n"
        "📊 <b>Statistika:</b>\n"
        "• /today — Bugungi reyting\n"
        "• /weekly — Haftalik reyting\n"
        "• /moreinfo — 🔎 Batafsil hisobot\n"
        "• /reset_today — 🧹 Bugungi statistikani tozalash"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=ReplyKeyboardRemove())

# ==========================================
# 📊 /moreinfo
# ==========================================
@dp.message(Command("moreinfo"))
@dp.channel_post(Command("moreinfo"))
async def cmd_moreinfo(message: types.Message):
    is_admin = message.from_user and message.from_user.id in ADMIN_IDS
    is_channel = message.chat.type == "channel"
    
    if not (is_admin or is_channel):
        return await message.answer("🔒 Bu ma'lumot faqat Admin uchun.")

    now = datetime.now(TIMEZONE)
    today_date = now.date()

    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT u.username, u.full_name, a.seconds, a.timestamp 
            FROM activity a 
            JOIN users u ON a.user_id = u.user_id 
            WHERE a.session_date = ? 
            ORDER BY a.timestamp ASC
        """, (today_date,))
        rows = await cursor.fetchall()

    if not rows:
        return await message.answer("📂 Bugun hali hech kim dars qilmadi.")

    report = defaultdict(list)
    for user, full_name, seconds, timestamp_str in rows:
        try:
            dt_obj = datetime.fromisoformat(str(timestamp_str))
            if dt_obj.tzinfo is None:
                dt_obj = pytz.utc.localize(dt_obj).astimezone(TIMEZONE)
            else:
                dt_obj = dt_obj.astimezone(TIMEZONE)
            end_time = dt_obj
        except: continue
        
        start_time = end_time - timedelta(seconds=seconds)
        time_range = f"{start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}"
        duration_fmt = format_time(seconds)
        display_name = f"@{user}" if user else full_name
        report[display_name].append(f"⏱ <code>{time_range}</code> ({duration_fmt})")

    text = "📊 <b>BATAFSIL KUNLIK HISOBOT</b>\n\n"
    for name, logs in report.items():
        safe_name = clean_name(name) 
        text += f"👤 <b>{safe_name}:</b>\n"
        for log in logs:
            text += f"   🔹 {log}\n"
        text += "\n"

    await message.answer(text, parse_mode="HTML")

# ==========================================
# 🧹 /reset_today
# ==========================================
@dp.message(Command("reset_today"))
@dp.channel_post(Command("reset_today"))
async def cmd_reset_today(message: types.Message):
    is_admin = message.from_user and message.from_user.id in ADMIN_IDS
    is_channel = message.chat.type == "channel"
    if not (is_admin or is_channel): return

    async with aiosqlite.connect(DB_NAME) as db:
        today = datetime.now(TIMEZONE).date()
        await db.execute("DELETE FROM activity WHERE session_date = ?", (today,))
        await db.commit()
    
    await message.answer("🧹 <b>Bugungi statistika tozalandi!</b> \nSessiyani 0 dan boshlashingiz mumkin.", parse_mode="HTML")

# ==========================================
# 🎮 START
# ==========================================
@dp.message(Command("start"))
@dp.channel_post(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user:
        await add_user(message.from_user)
    
    remove_kb = ReplyKeyboardRemove()
    is_admin = message.from_user and message.from_user.id in ADMIN_IDS
    is_channel = message.chat.type == "channel"

    if is_admin or is_channel:
        text = "👑 <b>Xush kelibsiz, Boss!</b>\n\nBuyruqlarni ko'rish uchun /help ni bosing."
        await message.answer(text, reply_markup=remove_kb, parse_mode="HTML")
    else:
        first_name = message.from_user.first_name if message.from_user else "Do'stim"
        text = (
            f"👋 <b>Salom, {clean_name(first_name)}!</b>\n\n"
            f"🍅 <b>Study With Me</b> botiga xush kelibsiz.\n"
            f"Admin sessiya boshlaganda <b>Join</b> tugmasini bosib qo'shiling.\n\n"
            f"Buyruqlar: /help"
        )
        await message.answer(text, reply_markup=remove_kb, parse_mode="HTML")

# ==========================================
# ⚙️ SESSISYA DVIJOK
# ==========================================
async def start_next_step(chat_id):
    if not session.queue:
        await finish_full_session(chat_id); return

    next_block = session.queue.pop(0)
    duration, b_type = next_block['duration'], next_block['type']
    end_time = datetime.now(TIMEZONE) + timedelta(minutes=duration)
    
    if b_type == 'study':
        session.status = "STUDY"
        for uid in session.active_participants: session.active_participants[uid] = datetime.now(TIMEZONE).timestamp()
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Join", callback_data="join_session"), InlineKeyboardButton(text="❌ Leave", callback_data="leave_session")]])
        await bot.send_message(chat_id, f"📚 <b>Study Session!</b>\n⏱ {duration} min.\n⬇️ Qo'shiling:", reply_markup=kb, parse_mode="HTML")
    elif b_type == 'break':
        session.status = "BREAK"
        await bot.send_message(chat_id, f"☕️ <b>Tanaffus!</b> ({duration} min)\nDam oling.", parse_mode="HTML")

    session.current_job = scheduler.add_job(end_current_block, 'date', run_date=end_time, args=[chat_id, b_type])

async def end_current_block(chat_id, b_type):
    if b_type == 'study':
        now = datetime.now(TIMEZONE).timestamp()
        for uid, start in session.active_participants.items():
            delta = int(now - start)
            if delta > 0: await log_activity(uid, delta)
        await bot.send_message(chat_id, "🛑 <b>Vaqt tugadi!</b>", parse_mode="HTML")
    await start_next_step(chat_id)

async def finish_full_session(chat_id):
    session.clear()
    await bot.send_message(chat_id, "🏁 <b>Sessiya yakunlandi!</b>", parse_mode="HTML")
    await send_leaderboard(chat_id, "today", "BUGUNGI NATIJALAR")

async def send_leaderboard(chat_id, period, title):
    data = await get_leaderboard_data(period)
    text = f"🏆 <b>{title}</b>\n\n"
    for i, (u, f, s) in enumerate(data, 1):
        raw_name = f"@{u}" if u else f"{f}"
        safe_name = clean_name(raw_name)
        text += f"{i}. {safe_name} — {format_time(s)} — {get_random_title()}\n"
    
    await bot.send_message(chat_id, text or "Ma'lumot yo'q", parse_mode="HTML")

# ==========================================
# 🕹 BUYRUQLAR (Kanalda ishlashi uchun moslandi)
# ==========================================
async def setup(msg, plan):
    is_admin = msg.from_user and msg.from_user.id in ADMIN_IDS
    is_channel = msg.chat.type == "channel"

    if not (is_admin or is_channel):
        return await msg.answer("❌ Bu buyruq faqat admin uchun!")
    
    if session.status != "IDLE": 
        return await msg.answer("⚠️ Sessiya allaqachon ketmoqda!")
    
    session.session_chat_id = msg.chat.id
    session.queue = plan
    await start_next_step(msg.chat.id)

@dp.message(Command("study25"))
@dp.channel_post(Command("study25"))
async def s25(m: types.Message): await setup(m, [{'type':'study','duration':25}, {'type':'break','duration':5}])

@dp.message(Command("study50"))
@dp.channel_post(Command("study50"))
async def s50(m: types.Message): await setup(m, [{'type':'study','duration':50}, {'type':'break','duration':10}])

@dp.message(Command("study_full"))
@dp.channel_post(Command("study_full"))
async def s_full(m: types.Message): await setup(m, ([{'type':'study','duration':25}, {'type':'break','duration':5}] * 6))

@dp.message(Command("study1"))
@dp.channel_post(Command("study1"))
async def s1(m: types.Message): await setup(m, ([{'type':'study','duration':50}, {'type':'break','duration':10}] * 3))

@dp.message(Command("end_session"))
@dp.channel_post(Command("end_session"))
async def end(m: types.Message):
    is_admin = m.from_user and m.from_user.id in ADMIN_IDS
    is_channel = m.chat.type == "channel"
    if not (is_admin or is_channel): return

    if session.status == "STUDY":
        now = datetime.now(TIMEZONE).timestamp()
        for uid, start in session.active_participants.items():
            d = int(now - start)
            if d > 0: await log_activity(uid, d)
    session.clear()
    await m.answer("🛑 To'xtatildi."); await send_leaderboard(m.chat.id, "today", "BUGUNGI NATIJALAR")

async def check_admin_and_send(message, period, title):
    is_admin = message.from_user and message.from_user.id in ADMIN_IDS
    is_channel = message.chat.type == "channel"
    
    if not (is_admin or is_channel):
        return await message.answer("🔒 Uzr, reytingni faqat Admin ko'ra oladi.")
    await send_leaderboard(message.chat.id, period, title)

@dp.message(Command("weekly"))
@dp.channel_post(Command("weekly"))
async def w(m): await check_admin_and_send(m, "weekly", "HAFTALIK REYTING")

@dp.message(Command("monthly"))
@dp.channel_post(Command("monthly"))
async def mn(m): await check_admin_and_send(m, "monthly", "OYLIK REYTING")

@dp.message(Command("today"))
@dp.channel_post(Command("today"))
async def td(m): await check_admin_and_send(m, "today", "BUGUNGI REYTING")

@dp.callback_query(F.data.in_({"join_session", "leave_session"}))
async def cb(call: types.CallbackQuery):
    uid = call.from_user.id
    if call.data == "join_session":
        await add_user(call.from_user)
        if session.status != "STUDY": return await call.answer("Tanaffusdamiz!", show_alert=True)
        if uid in session.active_participants: return await call.answer("Allaqachon qo'shilgansiz✅", show_alert=True)
        session.active_participants[uid] = datetime.now(TIMEZONE).timestamp()
        await call.answer("Qo'shildingiz!")
    else:
        if uid not in session.active_participants: return await call.answer("Chiqdingiz✅", show_alert=True)
        start = session.active_participants.pop(uid)
        await log_activity(uid, int(datetime.now(TIMEZONE).timestamp() - start))
        await call.answer("Chiqdingiz!")

async def main():
    await init_db(); scheduler.start()
    
    await bot.set_my_commands([
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="help", description="Buyruqlar ro'yxati")
    ])

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__": asyncio.run(main())