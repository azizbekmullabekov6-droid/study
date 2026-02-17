import aiosqlite
from datetime import datetime, timedelta
from loader import DB_NAME, TIMEZONE

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS activity (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, seconds INTEGER, session_date DATE, timestamp DATETIME)")
        await db.commit()

async def add_user(user):
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