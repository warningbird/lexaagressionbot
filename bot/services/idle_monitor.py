import asyncio
import logging
from datetime import datetime, timedelta, UTC

from aiogram import Bot

from config import load_config
from bot.text_utils import format_in_style


CFG = load_config()


async def idle_monitor_loop(bot: Bot, last_activity_by_chat: dict[int, datetime]) -> None:
    IDLE_THRESHOLD = timedelta(hours=CFG.idle_threshold_hours)
    CHECK_INTERVAL_SEC = CFG.idle_check_interval_sec
    toxic_templates = [
        "Ну и чё, ДОЛБОЕБЫ, работаем вообще? Или опять кофе-машину осаждаете?",
        "Хули вы зависли, ДОЛБОЕБЫ? Таски сами себя не закроют.",
        "ДОЛБОЕБЫ, дедлайны сами не сдвинутся. Шевелимся!",
    ]
    import random
    while True:
        try:
            if not CFG.enable_idle_monitor:
                await asyncio.sleep(CHECK_INTERVAL_SEC)
                continue
            now = datetime.now(UTC)
            for chat_id, last in list(last_activity_by_chat.items()):
                if now - last > IDLE_THRESHOLD:
                    core = random.choice(toxic_templates)
                    text = format_in_style(core, style="toxic")
                    try:
                        await bot.send_message(chat_id=chat_id, text=text)
                        last_activity_by_chat[chat_id] = now
                    except Exception:
                        logging.exception("idle_reminder_failed chat_id=%s", chat_id)
        except Exception:
            logging.exception("idle_monitor_error")
        await asyncio.sleep(CHECK_INTERVAL_SEC)


