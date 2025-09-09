from aiogram import Bot, Dispatcher

from bot.routers.groups import setup_group_router
from bot.routers.private import router as private_router
from bot.routers.reactions import router as reactions_router
from bot.routers.shared import setup_shared, start_idle_monitor


def build_app(bot: Bot) -> Dispatcher:
    dp = Dispatcher()
    setup_shared(bot)
    setup_group_router(dp, bot)
    dp.include_router(private_router)
    dp.include_router(reactions_router)
    return dp


def start_background_tasks(bot: Bot):
    return start_idle_monitor(bot)


