import os

# Provide dummy env so config.load_config() doesn't fail on import
os.environ.setdefault("BOT_TOKEN", "TEST_TOKEN")
os.environ.setdefault("OPENAI_API_KEY", "TEST_OPENAI_KEY")

from bot.routers.shared import build_user_prompt, pick_style_and_length
from bot.services.rate_limit import RateLimiter


def test_build_user_prompt_basic():
    text = build_user_prompt("привет мир", style="passive", length="short", greeting_ok=False)
    assert "привет мир" in text
    assert "кратким" in text or "кратким".upper() in text
    assert "Сразу к сути" in text


def test_pick_style_and_length_distribution():
    # smoke: function returns valid categories
    for _ in range(10):
        style, length = pick_style_and_length()
        assert style in {"toxic", "passive", "corp"}
        assert length in {"short", "normal"}


def test_rate_limiter():
    rl = RateLimiter(per_user_window_sec=5, per_user_max=1, per_chat_window_sec=10, per_chat_max=5)
    uid, chat = 123, 456
    assert rl.allow(uid, chat) is True
    assert rl.allow(uid, chat) is False  # immediate second should be blocked

