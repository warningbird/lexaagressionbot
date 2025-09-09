import os
from types import SimpleNamespace

# Provide dummy env so config.load_config() doesn't fail on import
os.environ.setdefault("BOT_TOKEN", "TEST_TOKEN")
os.environ.setdefault("OPENAI_API_KEY", "TEST_OPENAI_KEY")

from openai import OpenAIError, RateLimitError

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


class _FlakyClient:
    def __init__(self):
        self._calls = 0
        self.responses = SimpleNamespace(create=self._create)

    def _create(self, model: str, instructions: str, input: str, timeout: float):
        self._calls += 1
        if self._calls == 1:
            raise RateLimitError("rl")
        return SimpleNamespace(output_text="ok")


def test_openai_service_retry_on_ratelimit():
    svc = OpenAIService(client=_FlakyClient())
    out = svc.ask([
        {"role": "system", "content": "s"},
        {"role": "user", "content": "u"},
    ], max_retries=2, timeout_sec=0.1)
    assert out == "ok"


class _ErrorClient:
    def __init__(self, exc: Exception):
        self._exc = exc
        self.responses = SimpleNamespace(create=self._create)

    def _create(self, *a, **kw):
        raise self._exc


def test_openai_service_raises_openai_error():
    svc = OpenAIService(client=_ErrorClient(OpenAIError("boom")))
    raised = False
    try:
        svc.ask([{"role": "user", "content": "u"}], max_retries=1, timeout_sec=0.01)
    except OpenAIError:
        raised = True
    assert raised


def test_openai_service_raises_generic_error():
    svc = OpenAIService(client=_ErrorClient(Exception("x")))
    raised = False
    try:
        svc.ask([{"role": "user", "content": "u"}], max_retries=1, timeout_sec=0.01)
    except Exception as e:
        raised = True
        assert "x" in str(e)
    assert raised


