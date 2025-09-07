import asyncio
import logging
from aiogram import Bot
from dotenv import load_dotenv
from bot.logging_utils import configure_json_logging
from config import load_config

load_dotenv()
configure_json_logging(logging.INFO)

CFG = load_config()
BOT_TOKEN = CFG.bot_token

from bot.app import build_app, start_background_tasks
from bot.metrics import start_metrics_server
from bot.health import start_health_server

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = build_app(bot)
    # start metrics server on 9000
    start_metrics_server(9000)
    # start simple health server on 8080
    start_health_server(8080)
    start_background_tasks(bot)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        # graceful shutdown: close bot session
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())