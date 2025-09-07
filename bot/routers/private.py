from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ContentType, ChatType

from bot.routers.shared import handle_llm_request_shared
from bot.routers import shared as shared_ctx


router = Router()


@router.message(F.text)
async def private_trigger(m: Message):
    text = (m.text or "").strip()
    if text and not text.startswith("/"):
        await handle_llm_request_shared(m, text, reply_to_id=m.message_id)
    else:
        return


@router.message((F.chat.type == ChatType.PRIVATE) & (F.sticker | F.animation))
async def private_sticker_reply(m: Message):
    # Reply with sticker only if the user replies to bot's message
    if shared_ctx.STICKERS is None:
        return
    if not m.reply_to_message or not (m.reply_to_message.from_user and m.reply_to_message.from_user.is_bot):
        return
    await shared_ctx.STICKERS.send_random(chat_id=m.chat.id, reply_to_message_id=m.message_id)


