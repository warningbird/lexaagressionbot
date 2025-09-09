import os

# ensure env for config
os.environ.setdefault("BOT_TOKEN", "TEST_TOKEN")
os.environ.setdefault("OPENAI_API_KEY", "TEST_KEY")

from bot.routers.shared import build_user_prompt


def test_build_user_prompt_contains_it_rule():
    text = build_user_prompt("про рефакторинг", style="toxic", length="normal", greeting_ok=True)
    assert "Сам(а) ищи дальше" in text or "ищи дальше" in text


