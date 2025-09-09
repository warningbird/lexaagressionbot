import time

from bot.services.rate_limit import RateLimiter


def test_rate_limiter_per_user_and_chat_windows():
    rl = RateLimiter(per_user_window_sec=1, per_user_max=1, per_chat_window_sec=1, per_chat_max=2)
    uid, chat = 1, 100

    assert rl.allow(uid, chat) is True
    # user limited now
    assert rl.allow(uid, chat) is False

    # another user in same chat should still pass until per-chat cap
    assert rl.allow(2, chat) is True
    # chat limit reached
    assert rl.allow(3, chat) is False

    time.sleep(1.1)
    # windows expired
    assert rl.allow(uid, chat) is True


