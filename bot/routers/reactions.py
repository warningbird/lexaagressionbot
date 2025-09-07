from datetime import datetime, UTC

from aiogram import Router
from aiogram.types import MessageReactionUpdated

from bot.routers.shared import handle_llm_request_shared


router = Router()


@router.message_reaction()
async def on_reaction(event: MessageReactionUpdated):
    reactor = event.user
    if reactor is None:
        return
    mention = f"@{reactor.username}" if reactor.username else (reactor.full_name or "ты")

    # формируем текст задачи для LLM
    try:
        emojis = []
        if getattr(event, "new_reaction", None):
            for r in event.new_reaction:
                emoji = getattr(r, "emoji", None)
                if emoji:
                    emojis.append(emoji)
        reaction_str = " ".join(emojis) if emojis else "(реакция)"
    except Exception:
        reaction_str = "(реакция)"

    user_text = (
        f"Пользователь {mention} поставил реакцию {reaction_str} на сообщение бота. "
        f"Спроси резко и по делу, что ему нужно. Обязательно учитывай контекст сообщения. Обязательно учитывай реакцию."
    )

    # Оборачиваем в псевдо Message
    class _Proxy:
        pass

    proxy = _Proxy()
    proxy.chat = event.chat
    proxy.message_id = event.message_id
    proxy.from_user = reactor

    await handle_llm_request_shared(proxy, user_text, reply_to_id=event.message_id)


