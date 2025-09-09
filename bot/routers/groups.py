import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.enums import ChatType, ContentType
from aiogram.types import Message

from bot.openai_service import OpenAIService
from bot.prompts import SYSTEM_PROMPT
from bot.routers import shared as shared_ctx
from bot.routers.shared import handle_llm_request_shared

_OAI = OpenAIService()
_last_poll_on_date: dict[int, str] = {}


router = Router()


def setup_group_router(dp, bot: Bot):
    dp.include_router(router)


@router.message(F.text & (F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP})))
async def group_trigger(m: Message, bot: Bot):
    if m.from_user and m.from_user.is_bot:
        return
    text = m.text or ""
    if m.entities:
        for e in m.entities:
            if e.type == "mention":
                mention = text[e.offset : e.offset + e.length]
                me = await bot.get_me()
                if mention.lower().lstrip("@") == me.username.lower():
                    if m.reply_to_message:
                        quoted = (m.reply_to_message.text or m.reply_to_message.caption or "").strip()
                        if quoted:
                            await handle_llm_request_shared(m, quoted, reply_to_id=m.reply_to_message.message_id)
                            return
                    is_forward = any([
                        getattr(m, "forward_date", None),
                        getattr(m, "forward_from", None),
                        getattr(m, "forward_from_chat", None),
                        getattr(m, "forward_sender_name", None),
                        getattr(m, "forward_origin", None),
                    ])
                    if is_forward:
                        forwarded_text = (m.text or m.caption or "").replace(mention, "").strip()
                        if forwarded_text:
                            await handle_llm_request_shared(m, forwarded_text, reply_to_id=m.message_id)
                            return
                    q = text.replace(mention, "").strip() or (m.reply_to_message.text if m.reply_to_message else "") or (m.caption or "")
                    tl = (q or "").lower()
                    if "шмел" in tl:
                        today_key = datetime.now(ZoneInfo("Asia/Almaty")).date().isoformat()
                        last_key = _last_poll_on_date.get(m.chat.id)
                        if last_key == today_key:
                            try:
                                msg_texts = [
                                    {"role": "system", "content": SYSTEM_PROMPT},
                                    {"role": "user", "content": "Сгенерируй короткий токсичный ответ: сегодня уже голосовали по бару, хватит."},
                                ]
                                already = await asyncio.to_thread(_OAI.ask, msg_texts, shared_ctx.CFG.openai_model)
                            except Exception:
                                already = "Сегодня уже голосовали. Успокойся."
                            await bot.send_message(chat_id=m.chat.id, text=already, reply_to_message_id=m.message_id)
                            return
                        try:
                            intro_msgs = [
                                {"role": "system", "content": SYSTEM_PROMPT},
                                {"role": "user", "content": "Сгенерируй короткое токсичное приглашение в бар ‘Шмель’ для чата; упомяни, что дальше будет голосовалка. Без префиксов."},
                            ]
                            poll_msgs = [
                                {"role": "system", "content": SYSTEM_PROMPT},
                                {"role": "user", "content": "Сгенерируй ОДНУ короткую язвительную строку-вопрос для голосовалки: идут ли в бар ‘Шмель’. Без кавычек и префиксов. До 120 символов."},
                            ]
                            opt_yes_tail_msgs = [
                                {"role": "system", "content": SYSTEM_PROMPT},
                                {"role": "user", "content": "Сгенерируй КОРОТКИЙ токсичный хвост-обоснование для варианта 'иду' (до 30 символов). Без кавычек."},
                            ]
                            opt_no_tail_msgs = [
                                {"role": "system", "content": SYSTEM_PROMPT},
                                {"role": "user", "content": "Сгенерируй КОРОТКИЙ токсичный хвост-обоснование для варианта 'не иду' (до 30 символов). Без кавычек."},
                            ]
                            intro = await asyncio.to_thread(_OAI.ask, intro_msgs, shared_ctx.CFG.openai_model)
                            question = await asyncio.to_thread(_OAI.ask, poll_msgs, shared_ctx.CFG.openai_model)
                            tail_yes = await asyncio.to_thread(_OAI.ask, opt_yes_tail_msgs, shared_ctx.CFG.openai_model)
                            tail_no = await asyncio.to_thread(_OAI.ask, opt_no_tail_msgs, shared_ctx.CFG.openai_model)
                            if not intro or not intro.strip():
                                raise ValueError("empty intro")
                            if not question or not question.strip():
                                raise ValueError("empty question")
                            tail_yes = (tail_yes or "").strip()
                            tail_no = (tail_no or "").strip()
                        except Exception:
                            intro = "Голосуем."
                            question = "В бар ‘Шмель’ идёшь?"
                            tail_yes = "иду"
                            tail_no = "не иду"

                        if not question:
                            question = "В бар ‘Шмель’ идёшь?"
                        if len(question) > 300:
                            question = question[:300]
                        tail_yes = (tail_yes or "").strip().strip('"').strip("'")
                        tail_no = (tail_no or "").strip().strip('"').strip("'")
                        opt_yes = f"иду — {tail_yes}" if tail_yes else "иду"
                        opt_no = f"не иду — {tail_no}" if tail_no else "не иду"
                        if len(opt_yes) > 50:
                            opt_yes = opt_yes[:50]
                        if len(opt_no) > 50:
                            opt_no = opt_no[:50]

                        try:
                            msg_intro = await bot.send_message(chat_id=m.chat.id, text=intro, reply_to_message_id=m.message_id)
                            shared_ctx._bot_messages_by_chat.setdefault(m.chat.id, set()).add(msg_intro.message_id)
                        except Exception:
                            pass

                        try:
                            poll = await bot.send_poll(
                                chat_id=m.chat.id,
                                question=question,
                                options=[opt_yes, opt_no],
                                is_anonymous=False,
                                allows_multiple_answers=False,
                            )
                            shared_ctx._bot_messages_by_chat.setdefault(m.chat.id, set()).add(poll.message_id)
                            _last_poll_on_date[m.chat.id] = today_key
                        except Exception:
                            try:
                                msg_fallback = await bot.send_message(chat_id=m.chat.id, text=f"{question}\n\nВарианты: {opt_yes} / {opt_no}")
                                shared_ctx._bot_messages_by_chat.setdefault(m.chat.id, set()).add(msg_fallback.message_id)
                                _last_poll_on_date[m.chat.id] = today_key
                            except Exception:
                                pass
                        return
                    await handle_llm_request_shared(m, q, reply_to_id=m.message_id)
                    return
    


@router.message((F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP})) & ((F.content_type == ContentType.STICKER) | (F.content_type == ContentType.ANIMATION)))
async def group_sticker_reply(m: Message):
    if shared_ctx.STICKERS is None:
        return
    # Only react if it's a reply to bot's message
    if not m.reply_to_message or not (m.reply_to_message.from_user and m.reply_to_message.from_user.is_bot):
        return
    await shared_ctx.STICKERS.send_random(chat_id=m.chat.id, reply_to_message_id=m.message_id)


