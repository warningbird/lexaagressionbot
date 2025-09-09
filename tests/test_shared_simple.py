import os

# minimal env for config on import in modules
os.environ.setdefault("BOT_TOKEN", "TEST_TOKEN")
os.environ.setdefault("OPENAI_API_KEY", "TEST_OPENAI_KEY")

from bot.prompts import SYSTEM_PROMPT
from bot.routers.shared import pick_style_and_length
from bot.text_utils import format_in_style


def test_pick_style_and_length_fixed():
    style, length = pick_style_and_length()
    assert style == "toxic"
    assert length == "normal"


def test_format_in_style_no_footer():
    assert format_in_style("core", style="toxic") == "core"


def test_system_prompt_contains_rules():
    text = SYSTEM_PROMPT
    assert "ПЕРЕД ОТВЕТОМ ПРОАНАЛИЗИРУЙ" in text
    assert "выкрути токсичность на максимум" in text
    assert "Сам(а) ищи дальше" in text


