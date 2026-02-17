from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove, BufferedInputFile
from datetime import datetime, timedelta
from collections import defaultdict
import aiosqlite
import pytz 
import asyncio

# Biz yaratgan boshqa fayllardan kodlarni chaqiramiz
from loader import bot, scheduler, ADMIN_IDS, TIMEZONE, DB_NAME
import database as db
from utils import session, format_time, get_random_title, clean_name, get_rank_info, create_activity_graph

router = Router()

# --- MANTIQIY FUNKSIYALAR ---

async def start_next_step(chat_id):
    """
    Bu funksiya navbatdagi dars yoki tanaffusni boshlaydi.
    MUHIM: Har yangi bosqichda ro'yxatni tozalaydi (Anti-Cheat).
    """
    if not session.queue:
        await finish_full_session(chat_id); return

    # --- O'ZGARISH: ANTI-CHEAT TIZIMI ---
    # Har yangi bosqich (dars yoki tanaffus) boshlanganda ro'yxatni tozalaymiz.
    # Shunda foydalanuvchi "Join" ni qaytadan bosishi majburiy bo'ladi.
    session.active_participants.clear()
    # -----------------------------------

    next_block = session.queue.pop(0)
    duration, b_type = next_block['duration'], next_block['type']
    end_time = datetime.now(TIMEZONE) + timedelta(minutes=duration)
    
    if b_type == 'study':
        session.status = "STUDY"
        # Ro'yxat bo'sh, shuning uchun hech kimga vaqt yozishni boshlamaymiz hali.
        
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Join", callback_data="join_session")], [InlineKeyboardButton(text="❌ Leave", callback_data="leave_session")]])
        
        # 1. Asosiy Study xabari
        await bot.send_message(chat_id, f"📚 <b>Study Session Started!</b>\n⏱ {duration} min.\n⬇️ Join or Leave", reply_markup=kb, parse_mode="HTML")
        
        # 2. VAQT BOTI UCHUN BUYRUQ
        await bot.send_message(chat_id, f"/{duration}")

    elif b_type == 'break':
        session.status = "BREAK"
        # Tanaffusda ham ro'yxat bo'sh bo'ladi.
        
        # 1. Asosiy Tanaffus xabari
        await bot.send_message(chat_id, f"☕️ <b>Break time!</b> ({duration} min)\nTake a break.", parse_mode="HTML")

        # 2. VAQT BOTI UCHUN BUYRUQ
        await bot.send_message(chat_id, f"/{duration}")

    session.current_job = scheduler.add_job(end_current_block, 'date', run_date=end_time, args=[chat_id, b_type])

async def end_current_block(chat_id, b_type):
    """
    Dars yoki tanaffus tugaganda ishlaydi.
    Hozirgi qatnashuvchilarning vaqtini hisoblab bazaga yozadi.
    """
    if b_type == 'study':
        now = datetime.now(TIMEZONE).timestamp()
        
        # Kimki ro'yxatda bor bo'lsa (demak Leave qilmagan), ularning vaqtini yozamiz
        for uid, start in session.active_participants.items():
            delta = int(now - start)
            if delta > 0: await db.log_activity(uid, delta)
        
        await bot.send_message(chat_id, "🛑 <b>Time is up!</b>", parse_mode="HTML")
    
    # Keyingi bosqichga o'tish (Funksiya ichida start_next_step chaqiriladi, 
    # u esa ro'yxatni tozalab tashlaydi)
    await start_next_step(chat_id)

async def finish_full_session(chat_id):
    session.clear()
    await bot.send_message(chat_id, "🏁 <b>The session has ended!</b>", parse_mode="HTML")
    await send_leaderboard(chat_id, "today", "LEADERBOARD")
    
    # Avtomatik /today buyrug'ini yuborish
    await bot.send_message(chat_id, "/today")

async def send_leaderboard(chat_id, period, title):
    data = await db.get_leaderboard_data(period)
    text = f"🏆 <b>{title}</b>\n\n"
    for i, (u, f, s) in enumerate(data, 1):
        raw_name = f"@{u}" if u else f"{f}"
        safe_name = clean_name(raw_name)
        text += f"{i}. {safe_name} — {format_time(s)} — {get_random_title()}\n"
    await bot.send_message(chat_id, text or "No info", parse_mode="HTML")

async def setup(msg, plan):
    is_admin = msg.from_user and msg.from_user.id in ADMIN_IDS
    is_channel = msg.chat.type == "channel"
    if not (is_admin or is_channel): return await msg.answer("❌ Admin only!")
    if session.status != "IDLE": return await msg.answer("⚠️The session is in progress!")
    session.session_chat_id = msg.chat.id
    session.queue = plan
    await start_next_step(msg.chat.id)

async def check_admin_and_send(message, period, title):
    is_admin = message.from_user and message.from_user.id in ADMIN_IDS
    is_channel = message.chat.type == "channel"
    if not (is_admin or is_channel):
        return await message.answer("🔒 Sorry, only the Admin can view the ranking.")
    await send_leaderboard(message.chat.id, period, title)

# --- BUYRUQLAR (HANDLERS) ---

@router.message(Command("start"))
@router.channel_post(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user: await db.add_user(message.from_user)
    remove_kb = ReplyKeyboardRemove()
    is_admin = message.from_user and message.from_user.id in ADMIN_IDS
    is_channel = message.chat.type == "channel"

    if is_admin or is_channel:
        await message.answer("👑 <b>Boss!</b> click the /help .", reply_markup=remove_kb, parse_mode="HTML")
    else:
        name = message.from_user.first_name if message.from_user else "Dostim"
        await message.answer(f"👋 <b>Salom, {clean_name(name)}!</b>\nCommands:\n/rank - My level\n/graph - My graph\n/help - Help", reply_markup=remove_kb, parse_mode="HTML")

@router.message(Command("help"))
@router.channel_post(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        "🆘 <b>COMMAND LIST</b>\n\n"
        "👤 <b>User:</b>\n"
        "• /rank — My level and score\n"
        "• /graph — Today's activity chart 📊\n\n"
        "👑 <b>Admin:</b>\n"
        "• /study25 — 25+5\n• /study50 — 50+10\n• /study_full — 25+5 (x6)\n• /end_session — Stop\n\n"
        "📊 <b>Statistics:</b>\n"
        "• /today, /yesterday, /weekly\n• /moreinfo — Hisobot\n• /reset_today — Tozalash"
    )
    await message.answer(text, parse_mode="HTML")

# --- UNVONNI KO'RISH (/rank) ---
@router.message(Command("rank"))
@router.channel_post(Command("rank"))
async def cmd_rank(message: types.Message):
    if not message.from_user: return
    user_id = message.from_user.id
    
    total_minutes = 0
    async with aiosqlite.connect(DB_NAME) as dbo:
        cursor = await dbo.execute("SELECT SUM(seconds) FROM activity WHERE user_id = ?", (user_id,))
        result = await cursor.fetchone()
        if result and result[0]:
            total_minutes = result[0] // 60
            
    (rank_limit, rank_name, rank_desc), next_rank = get_rank_info(total_minutes)
    
    name = message.from_user.first_name
    text = f"👤 <b>{clean_name(name)}ning statusi:</b>\n\n"
    text += f"🏅 <b>{rank_name}</b>\n"
    text += f"💬 <i>{rank_desc}</i>\n\n"
    text += f"⏱ Total Study Time: <b>{format_time(total_minutes * 60)}</b>\n"
    
    if next_rank:
        left = next_rank[0] * 60 - total_minutes
        text += f"🚀 Time remaining to reach the next level: {format_time(left * 60)}."
    else:
        text += "👑 You have reached the highest level!"
    
    await message.answer(text, parse_mode="HTML")

# --- GRAFIK CHIZISH (/graph) ---
@router.message(Command("graph"))
@router.channel_post(Command("graph"))
async def cmd_graph(message: types.Message):
    if not message.from_user: return
    await message.answer("📊 <b>The chart is being generated...</b>", parse_mode="HTML")
    
    today = datetime.now(TIMEZONE).date()
    data_dict = defaultdict(int)
    
    async with aiosqlite.connect(DB_NAME) as dbo:
        cursor = await dbo.execute("""
            SELECT timestamp, seconds FROM activity 
            WHERE session_date = ? AND user_id = ?
        """, (today, message.from_user.id))
        rows = await cursor.fetchall()
        
    if not rows:
        return await message.answer("You have not studied today yet 📉")

    for ts, seconds in rows:
        try:
            dt = datetime.fromisoformat(str(ts))
            if dt.tzinfo is None: dt = pytz.utc.localize(dt).astimezone(TIMEZONE)
            else: dt = dt.astimezone(TIMEZONE)
            hour_key = dt.strftime("%H:00")
            data_dict[hour_key] += (seconds // 60)
        except: continue

    photo_bytes = await asyncio.to_thread(create_activity_graph, data_dict, f"Today's Activity ({today})")
    
    if photo_bytes:
        file = BufferedInputFile(photo_bytes.read(), filename="chart.png")
        await message.answer_photo(photo=file, caption=f"📈 {message.from_user.first_name}, Your today's result!")
    else:
        await message.answer("An error occurred.")

# --- DARS BUYRUQLARI ---

@router.message(Command("study25"))
@router.channel_post(Command("study25"))
async def s25(m: types.Message): await setup(m, [{'type':'study','duration':25}, {'type':'break','duration':5}])

@router.message(Command("study50"))
@router.channel_post(Command("study50"))
async def s50(m: types.Message): await setup(m, [{'type':'study','duration':50}, {'type':'break','duration':10}])

@router.message(Command("study_full"))
@router.channel_post(Command("study_full"))
async def s_full(m: types.Message): await setup(m, ([{'type':'study','duration':25}, {'type':'break','duration':5}] * 6))

@router.message(Command("study1"))
@router.channel_post(Command("study1"))
async def s1(m: types.Message): await setup(m, ([{'type':'study','duration':50}, {'type':'break','duration':10}] * 3))

@router.message(Command("end_session"))
@router.channel_post(Command("end_session"))
async def end(m: types.Message):
    is_admin = m.from_user and m.from_user.id in ADMIN_IDS
    is_channel = m.chat.type == "channel"
    if not (is_admin or is_channel): return
    
    # Agar STUDY payti to'xtatilsa, shu paytgacha bo'lgan vaqtni saqlab qo'yamiz
    if session.status == "STUDY":
        now = datetime.now(TIMEZONE).timestamp()
        for uid, start in session.active_participants.items():
            d = int(now - start)
            if d > 0: await db.log_activity(uid, d)
            
    session.clear()
    await m.answer("🛑 Stopped."); await send_leaderboard(m.chat.id, "today", "LEADERBOARD")

@router.message(Command("weekly"))
@router.channel_post(Command("weekly"))
async def w(m): await check_admin_and_send(m, "weekly", "WEEKLY LEADERBOARD")

@router.message(Command("monthly"))
@router.channel_post(Command("monthly"))
async def mn(m): await check_admin_and_send(m, "monthly", "MONTHLY LEADERBOARD")

@router.message(Command("today"))
@router.channel_post(Command("today"))
async def td(m): await check_admin_and_send(m, "today", "TODAY'S LEADERBOARD")

@router.message(Command("reset_today"))
@router.channel_post(Command("reset_today"))
async def cmd_reset_today(message: types.Message):
    is_admin = message.from_user and message.from_user.id in ADMIN_IDS
    is_channel = message.chat.type == "channel"
    if not (is_admin or is_channel): return
    async with aiosqlite.connect(DB_NAME) as dbo:
        today = datetime.now(TIMEZONE).date()
        await dbo.execute("DELETE FROM activity WHERE session_date = ?", (today,))
        await dbo.commit()
    await message.answer("🧹 <b>Todays's statistics cleared!</b>", parse_mode="HTML")

@router.message(Command("moreinfo"))
@router.channel_post(Command("moreinfo"))
async def cmd_moreinfo(message: types.Message):
    is_admin = message.from_user and message.from_user.id in ADMIN_IDS
    is_channel = message.chat.type == "channel"
    if not (is_admin or is_channel): return await message.answer("🔒 Admin only.")

    now = datetime.now(TIMEZONE)
    today_date = now.date()
    async with aiosqlite.connect(DB_NAME) as dbo:
        cursor = await dbo.execute("""SELECT u.username, u.full_name, a.seconds, a.timestamp 
            FROM activity a JOIN users u ON a.user_id = u.user_id WHERE a.session_date = ? ORDER BY a.timestamp ASC""", (today_date,))
        rows = await cursor.fetchall()

    if not rows: return await message.answer("📂 Empty.")
    report = defaultdict(list)
    for user, full_name, seconds, timestamp_str in rows:
        try:
            dt_obj = datetime.fromisoformat(str(timestamp_str))
            if dt_obj.tzinfo is None: dt_obj = pytz.utc.localize(dt_obj).astimezone(TIMEZONE)
            else: dt_obj = dt_obj.astimezone(TIMEZONE)
            end_time = dt_obj
        except: continue
        start_time = end_time - timedelta(seconds=seconds)
        time_range = f"{start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}"
        display_name = f"@{user}" if user else full_name
        report[display_name].append(f"⏱ <code>{time_range}</code> ({format_time(seconds)})")

    text = "📊 <b>DETAILS</b>\n\n"
    for name, logs in report.items():
        text += f"👤 <b>{clean_name(name)}:</b>\n" + "".join([f"   🔹 {log}\n" for log in logs]) + "\n"
    await message.answer(text, parse_mode="HTML")

# --- CALLBACKS (Tugmalar) ---
@router.callback_query(F.data.in_({"join_session", "leave_session"}))
async def cb(call: types.CallbackQuery):
    uid = call.from_user.id
    
    # --- JOIN (Qo'shilish) ---
    if call.data == "join_session":
        await db.add_user(call.from_user)
        if session.status != "STUDY": return await call.answer("Break time!", show_alert=True)
        if uid in session.active_participants: return await call.answer("You have already joined✅", show_alert=True)
        
        # Yangi qo'shilgan vaqtini belgilaymiz
        session.active_participants[uid] = datetime.now(TIMEZONE).timestamp()
        await call.answer("You have joined successfully!")
    
    # --- LEAVE (Chiqish) ---
    else:
        if uid not in session.active_participants: return await call.answer("You are not on the list!", show_alert=True)
        
        start = session.active_participants.pop(uid)
        
        # Faqat STUDY paytida chiqsa vaqtni yozamiz
        if session.status == "STUDY":
            delta = int(datetime.now(TIMEZONE).timestamp() - start)
            if delta > 0: await db.log_activity(uid, delta)

        await call.answer("You have left!")

# --- KECHAGI KUN STATISTIKASI (/yesterday) ---
@router.message(Command("yesterday"))
@router.channel_post(Command("yesterday"))
async def cmd_yesterday(message: types.Message):
    is_admin = message.from_user and message.from_user.id in ADMIN_IDS
    is_channel = message.chat.type == "channel"
    if not (is_admin or is_channel):
        return await message.answer("🔒 Bu buyruq faqat admin uchun.")

    yesterday = (datetime.now(TIMEZONE) - timedelta(days=1)).date()
    
    async with aiosqlite.connect(DB_NAME) as dbo:
        cursor = await dbo.execute("""
            SELECT u.full_name, u.username, SUM(a.seconds)
            FROM activity a 
            JOIN users u ON a.user_id = u.user_id 
            WHERE a.session_date = ? 
            GROUP BY a.user_id
            ORDER BY SUM(a.seconds) DESC
        """, (yesterday,))
        rows = await cursor.fetchall()

    if not rows:
        return await message.answer(f"📅 <b>{yesterday}</b> sanasida hech kim dars qilmagan ekan.", parse_mode="HTML")

    text = f"📅 <b>YESTERDAY'S ACTIVITY ({yesterday})</b>\n\n"
    for i, (full_name, username, seconds) in enumerate(rows, 1):
        raw_name = f"@{username}" if username else full_name
        text += f"{i}. {clean_name(raw_name)} — {format_time(seconds)}\n"

    await message.answer(text, parse_mode="HTML")