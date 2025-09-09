import os
from types import SimpleNamespace

# Provide dummy env so config.load_config() doesn't fail on import
os.environ.setdefault("BOT_TOKEN", "TEST_TOKEN")
os.environ.setdefault("OPENAI_API_KEY", "TEST_OPENAI_KEY")

from bot.openai_service import OpenAIService


class _DummyClient:
    def __init__(self, text: str = "ok"):
        self._text = text
        self.responses = SimpleNamespace(create=self._create)

    def _create(self, model: str, instructions: str, input: str, timeout: float):
        return SimpleNamespace(output_text=f"[{model}] {instructions}|{input}")


def test_openai_service_ask_happy_path():
    svc = OpenAIService(client=_DummyClient())
    msg = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hello"},
        {"role": "user", "content": "world"},
    ]
    out = svc.ask(msg, model="dummy-model", timeout_sec=0.1, max_retries=1)
    assert "dummy-model" in out
    assert "sys" in out
    assert "hello" in out and "world" in out


