import asyncio
import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot

from bot.openai_service import OpenAIService
from bot.text_utils import format_in_style
from config import load_config

CFG = load_config()

_last_weekly_alert_on_date: dict[int, str] = {}


async def idle_monitor_loop(bot: Bot, last_activity_by_chat: dict[int, datetime]) -> None:
    IDLE_THRESHOLD = timedelta(hours=CFG.idle_threshold_hours)
    CHECK_INTERVAL_SEC = CFG.idle_check_interval_sec
    oai = OpenAIService()
    while True:
        try:
            if not CFG.enable_idle_monitor:
                await asyncio.sleep(CHECK_INTERVAL_SEC)
                continue
            now = datetime.now(UTC)
            now_almaty = datetime.now(ZoneInfo("Asia/Almaty"))
            is_weekly_window = (now_almaty.weekday() == 4 and now_almaty.hour == 9 and now_almaty.minute < 10)
            today_key = now_almaty.date().isoformat()
            for chat_id, last in list(last_activity_by_chat.items()):
                # Weekly Friday 09:00 Asia/Almaty reminder (once per Friday)
                if is_weekly_window and _last_weekly_alert_on_date.get(chat_id) != today_key:
                    weekly_messages = [
                        {"role": "system", "content": (
                            "Ты — LexaAgressionAI. Отвечай максимально токсично, по делу, без префиксов. Язык: русский."
                        )},
                        {"role": "user", "content": (
                            "Сгенерируй жёсткое токсичное напоминание в пятницу утром: закрыть задачи и списать время."
                        )},
                    ]
                    try:
                        weekly_core = await asyncio.to_thread(oai.ask, weekly_messages, CFG.openai_model)
                    except Exception:
                        weekly_core = "Закрываем задачи и списываем время. Быстро."
                    try:
                        await bot.send_message(chat_id=chat_id, text=weekly_core)
                        _last_weekly_alert_on_date[chat_id] = today_key
                    except Exception:
                        logging.exception("weekly_reminder_failed chat_id=%s", chat_id)

                if now - last > IDLE_THRESHOLD:
                    messages = [
                        {"role": "system", "content": (
                            "Ты — LexaAgressionAI. Отвечай токсично и по делу, без префиксов. Язык: русский."
                        )},
                        {"role": "user", "content": (
                            "Сгенерируй очень краткое токсичное напоминание, что в чате давно тишина и пора работать."
                        )},
                    ]
                    try:
                        core = await asyncio.to_thread(oai.ask, messages, CFG.openai_model)
                    except Exception:
                        core = "Активность нулевая. Пора шевелиться."
                    text = format_in_style(core, style="toxic")
                    try:
                        await bot.send_message(chat_id=chat_id, text=text)
                        last_activity_by_chat[chat_id] = now
                    except Exception:
                        logging.exception("idle_reminder_failed chat_id=%s", chat_id)
        except Exception:
            logging.exception("idle_monitor_error")
        await asyncio.sleep(CHECK_INTERVAL_SEC)


