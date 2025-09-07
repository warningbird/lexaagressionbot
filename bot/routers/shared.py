import asyncio
import logging
from datetime import datetime, timedelta, UTC
from typing import Optional

from aiogram import Bot
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender
from aiogram import exceptions as tg_exc

from config import load_config
from bot.prompts import SYSTEM_PROMPT, AVATAR_ROAST_INSTRUCTION
from bot.text_utils import format_in_style
from bot.openai_service import OpenAIService
from bot.services.rate_limit import RateLimiter
from bot.services.stickers import StickerService
from bot.logging_utils import log_with_context
from bot.services.idle_monitor import idle_monitor_loop
from bot.metrics import REQUESTS, RESPONSES, ERRORS, RATE_LIMITED, LLM_LATENCY, ACTIVE_CHATS
from openai import OpenAIError, RateLimitError


CFG = load_config()

# Runtime state
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
    import random
    r = random.random()
    if r < CFG.passive_probability:
        style = "passive"
    elif r < (CFG.passive_probability + CFG.corp_probability):
        style = "corp"
    else:
        style = "toxic"
    length = "short" if random.random() < CFG.short_reply_probability else "normal"
    return style, length


def build_user_prompt(user_text: str, style: str, length: str, mention: Optional[str] = None, greeting_ok: bool = True) -> str:
    parts: list[str] = []
    if mention:
        parts.append(f"Адресуйся к {mention} в тексте, если уместно.")
    if style == "toxic":
        parts.append("Сохраняй исходный токсичный стиль системного промпта.")
    elif style == "passive":
        parts.append("Используй лютую пассивную агрессию и сарказм, колкие пассивные уколы. Без мата и без прямых оскорблений.")
    elif style == "corp":
        parts.append("Ответь в стиле корпоративной бюрократии: максимально многословно, витиевато, туманно и пустословно. Без мата и без прямых оскорблений.")
    if length == "short":
        parts.append("Сделай ответ кратким (одно-два абзаца максимум).")
    if not greeting_ok:
        parts.append("Не приветствуйся и не делай вступлений. Сразу к сути.")
    parts.append(f"Текст пользователя: {user_text}")
    return " \n".join(parts)


async def handle_llm_request_shared(m: Message, user_text: str, reply_to_id: int | None = None):
    if _bot is None or STICKERS is None:
        return

    # Rate limits (per user/chat)
    uid = m.from_user.id if m.from_user else 0
    if not RATE.allow(uid, m.chat.id):
        RATE_LIMITED.inc()
        try:
            sent = await _bot.send_message(chat_id=m.chat.id, text="Поуймись, очередь. Подожди пару секунд.", reply_to_message_id=(reply_to_id or m.message_id))
            _bot_messages_by_chat.setdefault(m.chat.id, set()).add(sent.message_id)
        except Exception:
            pass
        return

    async with ChatActionSender.typing(bot=_bot, chat_id=m.chat.id):
        # greeting suppression
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
            LLM_LATENCY.observe(time.monotonic() - _t0)
        except RateLimitError:
            ERRORS.labels(kind="ratelimit").inc()
            log_with_context(logging.WARNING, "llm_ratelimit", chat_id=m.chat.id)
            answer = format_in_style(
                "ЛИМИТ ВЫ ЖРАНУЛИ ДО ДНА ДОЛБОЕБЫ. Квота закончилась — пополните баланс или подождите, пока отвиснет."
            , style=style)
        except OpenAIError as e:
            ERRORS.labels(kind="openai").inc()
            log_with_context(logging.ERROR, "llm_openai_error", chat_id=m.chat.id, error=str(e)[:200])
            answer = format_in_style(
                f"МОДЕЛЬ ЗАДОХНУЛАСЬ, БЛЯТЬ. Техническая ошибка LLM: {str(e)[:120]} — чините свой цирк или ждите."
            , style=style)
        except Exception as e:
            ERRORS.labels(kind="unexpected").inc()
            logging.exception("llm_unexpected_error")
            answer = format_in_style(
                f"ВСЁ ПОШЛО ПО ПИЗДЕ НЕОЖИДАННО. Ошибка: {str(e)[:120]} — повторите позже."
            , style=style)

    target_reply_id = reply_to_id or m.message_id

    # optional avatar roast
    if CFG.enable_roast:
        try:
            import random
            avatar_roast = None
            user = m.from_user
            has_avatar = False
            if user:
                photos = await _bot.get_user_profile_photos(user.id, limit=CFG.avatar_photos_limit)
                has_avatar = photos.total_count > 0
            # per-user roast cooldown
            last_roast = _last_greet_at_by_user.get(user.id) if user else None
            roast_allowed = True
            if last_roast and now - last_roast < timedelta(hours=CFG.roast_cooldown_hours):
                roast_allowed = False
            if has_avatar and roast_allowed and random.random() < CFG.roast_probability:
                prompt_for_avatar = build_user_prompt(AVATAR_ROAST_INSTRUCTION, style, "short", greeting_ok=False)
                avatar_messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt_for_avatar},
                ]
                try:
                    avatar_roast = await asyncio.to_thread(OAI.ask, avatar_messages, CFG.openai_model)
                except Exception:
                    avatar_roast = None
            if avatar_roast:
                answer = f"{answer}\n\nP.S. {avatar_roast.strip()}"
        except Exception:
            pass

    # (GIF replies on incoming animations are handled in routers; no random GIFs here)

    # send reply (chunking)
    if len(answer) > CFG.telegram_chunk_size:
        chunks = [answer[i:i+CFG.telegram_chunk_size] for i in range(0, len(answer), CFG.telegram_chunk_size)]
        for ch in chunks:
            try:
                msg = await _bot.send_message(chat_id=m.chat.id, text=ch, reply_to_message_id=target_reply_id)
            except tg_exc.TelegramRetryAfter as e:
                await asyncio.sleep(getattr(e, "retry_after", 1) or 1)
                msg = await _bot.send_message(chat_id=m.chat.id, text=ch, reply_to_message_id=target_reply_id)
            except tg_exc.TelegramBadRequest:
                msg = None
            _bot_messages_by_chat.setdefault(m.chat.id, set()).add(msg.message_id)
            RESPONSES.labels(type="text").inc()
    else:
        try:
            msg = await _bot.send_message(chat_id=m.chat.id, text=answer, reply_to_message_id=target_reply_id)
        except tg_exc.TelegramRetryAfter as e:
            await asyncio.sleep(getattr(e, "retry_after", 1) or 1)
            msg = await _bot.send_message(chat_id=m.chat.id, text=answer, reply_to_message_id=target_reply_id)
        except tg_exc.TelegramBadRequest:
            msg = None
        _bot_messages_by_chat.setdefault(m.chat.id, set()).add(msg.message_id)
        RESPONSES.labels(type="text").inc()

    # maybe send sticker and update last activity
    if CFG.enable_stickers:
        await STICKERS.maybe_send(chat_id=m.chat.id, reply_to_message_id=target_reply_id, every_nth=CFG.sticker_every_nth_reply, counter_by_chat=_reply_counter_by_chat)
    _last_activity_by_chat[m.chat.id] = datetime.now(UTC)
    ACTIVE_CHATS.set(len(_last_activity_by_chat))


def start_idle_monitor(bot: Bot) -> asyncio.Task:
    return asyncio.create_task(idle_monitor_loop(bot, _last_activity_by_chat))


