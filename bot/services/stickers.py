import logging

from aiogram import Bot


class StickerService:
    def __init__(self, bot: Bot, set_names: list[str]):
        self.bot = bot
        self.set_names = set_names
        self._cached_file_ids: list[str] = []

    async def ensure_loaded(self) -> None:
        if self._cached_file_ids:
            return
        for set_name in self.set_names:
            try:
                ss = await self.bot.get_sticker_set(name=set_name)
                self._cached_file_ids = [s.file_id for s in ss.stickers]
                logging.info("sticker_set_loaded %s count=%d", set_name, len(self._cached_file_ids))
                return
            except Exception:
                logging.exception("sticker_set_load_failed %s", set_name)

    async def maybe_send(self, chat_id: int, reply_to_message_id: int, every_nth: int, counter_by_chat: dict[int, int]) -> None:
        try:
            count = counter_by_chat.get(chat_id, 0) + 1
            counter_by_chat[chat_id] = count
            if every_nth <= 0 or count % every_nth != 0:
                return
            await self.ensure_loaded()
            if not self._cached_file_ids:
                return
            import random
            file_id = random.choice(self._cached_file_ids)
            await self.bot.send_sticker(chat_id=chat_id, sticker=file_id, reply_to_message_id=reply_to_message_id)
        except Exception:
            logging.exception("sticker_send_failed")

    async def send_random(self, chat_id: int, reply_to_message_id: int) -> None:
        try:
            await self.ensure_loaded()
            if not self._cached_file_ids:
                return
            import random
            file_id = random.choice(self._cached_file_ids)
            await self.bot.send_sticker(chat_id=chat_id, sticker=file_id, reply_to_message_id=reply_to_message_id)
        except Exception:
            logging.exception("sticker_send_failed")


