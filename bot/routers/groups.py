from datetime import datetime, UTC

from aiogram import Router, F, Bot
from aiogram.enums import ChatType, ContentType
from aiogram.types import Message

from bot.routers.shared import handle_llm_request_shared
from bot.routers import shared as shared_ctx


router = Router()


def setup_group_router(dp, bot: Bot):
    dp.include_router(router)


@router.message(F.text & (F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP})))
async def group_trigger(m: Message, bot: Bot):
    # Ignore messages from bots to prevent loops
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
                    q = text.replace(mention, "").strip() or "Ответь на это сообщение контекстно."
                    await handle_llm_request_shared(m, q, reply_to_id=m.message_id)
                    return
    # NOTE: last_activity update must be handled in shared handler after send
    # Just touch it here if needed
    # last_activity_by_chat[m.chat.id] = datetime.now(UTC)


@router.message((F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP})) & ((F.content_type == ContentType.STICKER) | (F.content_type == ContentType.ANIMATION)))
async def group_sticker_reply(m: Message):
    if shared_ctx.STICKERS is None:
        return
    # Only react if it's a reply to bot's message
    if not m.reply_to_message or not (m.reply_to_message.from_user and m.reply_to_message.from_user.is_bot):
        return
    await shared_ctx.STICKERS.send_random(chat_id=m.chat.id, reply_to_message_id=m.message_id)


