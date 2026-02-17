import asyncio
import logging
import sys
from aiogram.types import BotCommand
from loader import bot, dp, scheduler
import database as db
import handlers

# Loglarni yoqish (Terminalda ko'rinishi uchun)
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

async def main():
    print("🚀 Bot ishga tushirilmoqda...")

    # 1. Bazani yaratamiz
    await db.init_db()
    print("✅ Baza ulandi.")
    
    # 2. Vaqt dvijogini yoqamiz
    scheduler.start()
    print("✅ Vaqt hisoblagich yoqildi.")
    
    # 3. Routerlarni ulaymiz
    dp.include_router(handlers.router)
    
    # 4. Menyuni sozlaymiz
    await bot.set_my_commands([
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="help", description="Buyruqlar ro'yxati")
    ])

    # 5. Botni ishga tushiramiz
    print("🤖 Bot Telegram serveriga ulanmoqda...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot to'xtatildi!")