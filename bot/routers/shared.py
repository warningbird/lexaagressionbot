import asyncio
import logging
from datetime import UTC, datetime, timedelta

from aiogram import Bot
from aiogram import exceptions as tg_exc
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender
from openai import OpenAIError, RateLimitError

from bot.logging_utils import log_with_context
from bot.metrics import ACTIVE_CHATS, ERRORS, LLM_LATENCY, RATE_LIMITED, RESPONSES
from bot.openai_service import OpenAIService
from bot.prompts import SYSTEM_PROMPT
from bot.services.idle_monitor import idle_monitor_loop
from bot.services.rate_limit import RateLimiter
from bot.services.stickers import StickerService
from bot.text_utils import format_in_style
from config import load_config

CFG = load_config()
_bot: Bot | None = None
_reply_counter_by_chat: dict[int, int] = {}
_last_greet_at_by_user: dict[int, datetime] = {}
_last_activity_by_chat: dict[int, datetime] = {}
_bot_messages_by_chat: dict[int, set[int]] = {}

OAI = OpenAIService()
RATE = RateLimiter(
    per_user_window_sec=CFG.per_user_window_sec,
    per_user_max=CFG.per_user_max_requests,
    per_chat_window_sec=CFG.per_chat_window_sec,
    per_chat_max=CFG.per_chat_max_requests,
)
STICKERS: StickerService | None = None


def setup_shared(bot: Bot) -> None:
    global _bot, STICKERS
    _bot = bot
    STICKERS = StickerService(bot, list(CFG.sticker_set_candidates))


def pick_style_and_length() -> tuple[str, str]:
    style = "toxic"
    length = "normal"
    return style, length


def build_user_prompt(user_text: str, style: str, length: str, mention: str | None = None, greeting_ok: bool = True) -> str:
    parts: list[str] = []
    if mention:
        parts.append(f"Адресуйся к {mention} в тексте, если уместно.")
    if not greeting_ok:
        parts.append("Не приветствуйся и не делай вступлений. Сразу к сути.")
    parts.append(
        "Если тема относится к тестированию/качеству/менеджменту/айти/разработке/DevOps/архитектуре/данным или чему-то близкому — дай детальный ответ."
    )
    parts.append(
        "В конце добавь одну короткую строку с конкретными ключевыми словами/техниками, которые стоит поискать (начинай со слов ‘Сам(а) ищи дальше: …’)."
    )
    parts.append(f"Текст пользователя: {user_text}")
    return " \n".join(parts)


async def handle_llm_request_shared(m: Message, user_text: str, reply_to_id: int | None = None):
    if _bot is None or STICKERS is None:
        return

    uid = m.from_user.id if m.from_user else 0
    if not RATE.allow(uid, m.chat.id):
        RATE_LIMITED.inc()
        try:
            gen_messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "Сгенерируй короткую токсичную фразу, что очередь и нужно подождать несколько секунд."},
            ]
            gate_text = await asyncio.to_thread(OAI.ask, gen_messages, CFG.openai_model)
        except Exception:
            gate_text = "Очередь. Подожди."
        try:
            sent = await _bot.send_message(chat_id=m.chat.id, text=gate_text, reply_to_message_id=(reply_to_id or m.message_id))
            _bot_messages_by_chat.setdefault(m.chat.id, set()).add(sent.message_id)
        except Exception:
            pass
        return

    async with ChatActionSender.typing(bot=_bot, chat_id=m.chat.id):
        now = datetime.now(UTC)
        last = _last_greet_at_by_user.get(uid)
        greeting_ok = True
        if last and now - last < timedelta(hours=CFG.greet_suppress_hours):
            greeting_ok = False
        else:
            _last_greet_at_by_user[uid] = now

        style, length = pick_style_and_length()
        try:
            prompt_for_user = build_user_prompt(user_text, style, length, greeting_ok=greeting_ok)
            if len(prompt_for_user) > CFG.max_user_prompt_chars:
                prompt_for_user = prompt_for_user[:CFG.max_user_prompt_chars]
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt_for_user},
            ]
            import time
            _t0 = time.monotonic()
            answer = await asyncio.to_thread(OAI.ask, messages, CFG.openai_model)
            if not answer or not str(answer).strip():
                try:
                    gen_messages = [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": "Сгенерируй короткий токсичный ответ, что модель не вернула текста и пусть пользователь повторит запрос."},
                    ]
                    answer = await asyncio.to_thread(OAI.ask, gen_messages, CFG.openai_model)
                except Exception:
                    answer = format_in_style("Модель промолчала. Повтори запрос.", style="toxic")
            LLM_LATENCY.observe(time.monotonic() - _t0)
        except RateLimitError:
            ERRORS.labels(kind="ratelimit").inc()
            log_with_context(logging.WARNING, "llm_ratelimit", chat_id=m.chat.id)
            try:
                gen_messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": "Сгенерируй короткий токсичный ответ, что лимиты исчерпаны и нужно подождать."},
                ]
                answer = await asyncio.to_thread(OAI.ask, gen_messages, CFG.openai_model)
            except Exception:
                answer = format_in_style("Лимит. Подожди немного.", style=style)
        except OpenAIError as e:
            ERRORS.labels(kind="openai").inc()
            log_with_context(logging.ERROR, "llm_openai_error", chat_id=m.chat.id, error=str(e)[:200])
            try:
                gen_messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": "Сгенерируй короткий токсичный ответ, что у модели техническая ошибка и позже повторить."},
                ]
                answer = await asyncio.to_thread(OAI.ask, gen_messages, CFG.openai_model)
            except Exception:
                answer = format_in_style("Модель недоступна. Повтори позже.", style=style)
        except Exception:
            ERRORS.labels(kind="unexpected").inc()
            logging.exception("llm_unexpected_error")
            try:
                gen_messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": "Сгенерируй короткий токсичный ответ, что случился неожиданный сбой и нужно повторить позже."},
                ]
                answer = await asyncio.to_thread(OAI.ask, gen_messages, CFG.openai_model)
            except Exception:
                answer = format_in_style("Я хер его знает что произошло. Повтори позже.", style=style)

    target_reply_id = reply_to_id or m.message_id

    if len(answer) > CFG.telegram_chunk_size:
        answer = answer[:CFG.telegram_chunk_size]
    try:
        msg = await _bot.send_message(chat_id=m.chat.id, text=answer, reply_to_message_id=target_reply_id)
    except tg_exc.TelegramRetryAfter as e:
        await asyncio.sleep(getattr(e, "retry_after", 1) or 1)
        msg = await _bot.send_message(chat_id=m.chat.id, text=answer, reply_to_message_id=target_reply_id)
    except tg_exc.TelegramBadRequest:
        msg = None
    _bot_messages_by_chat.setdefault(m.chat.id, set()).add(msg.message_id)
    RESPONSES.labels(type="text").inc()

    if CFG.enable_stickers:
        await STICKERS.maybe_send(
            chat_id=m.chat.id,
            reply_to_message_id=target_reply_id,
            every_nth=CFG.sticker_every_nth_reply,
            counter_by_chat=_reply_counter_by_chat,
        )
    _last_activity_by_chat[m.chat.id] = datetime.now(UTC)
    ACTIVE_CHATS.set(len(_last_activity_by_chat))


def start_idle_monitor(bot: Bot) -> asyncio.Task:
    return asyncio.create_task(idle_monitor_loop(bot, _last_activity_by_chat))


