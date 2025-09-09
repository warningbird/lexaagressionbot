import asyncio
import os
from types import SimpleNamespace

# env for config
os.environ.setdefault("BOT_TOKEN", "TEST_TOKEN")
os.environ.setdefault("OPENAI_API_KEY", "TEST_OPENAI_KEY")

from aiogram.utils import chat_action as chat_action_mod

from bot.routers import shared as shared_mod


class _FakeMsg:
    def __init__(self, chat_id: int = 1, message_id: int = 10, user_id: int = 5):
        self.chat = SimpleNamespace(id=chat_id)
        self.message_id = message_id
        self.from_user = SimpleNamespace(id=user_id)


class _FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id: int, text: str, reply_to_message_id: int | None = None):
        self.sent.append((chat_id, text, reply_to_message_id))
        return SimpleNamespace(message_id=len(self.sent))


class _DummyStickers:
    async def maybe_send(self, **kwargs):
        return None


def test_handle_llm_rate_limited_path(monkeypatch):
    class _DummyTyping:
        def __init__(self, *a, **kw):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(chat_action_mod.ChatActionSender, "typing", _DummyTyping)

    fake_bot = _FakeBot()
    shared_mod._bot = fake_bot
    shared_mod.STICKERS = _DummyStickers()

    # force rate limit denied
    monkeypatch.setattr(shared_mod.RATE, "allow", lambda uid, cid: False)

    # force generated gate text
    class _O:
        def ask(self, *a, **kw):
            return "Очередь занята"

    shared_mod.OAI = _O()

    msg = _FakeMsg()
    asyncio.run(shared_mod.handle_llm_request_shared(msg, "test", reply_to_id=None))

    assert fake_bot.sent, "should send rate-limit message"
    assert "Очередь" in fake_bot.sent[0][1]


def test_handle_llm_happy_path_single_message(monkeypatch):
    class _DummyTyping:
        def __init__(self, *a, **kw):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(chat_action_mod.ChatActionSender, "typing", _DummyTyping)

    fake_bot = _FakeBot()
    shared_mod._bot = fake_bot

    # allow
    monkeypatch.setattr(shared_mod.RATE, "allow", lambda uid, cid: True)

    class _O:
        def ask(self, *a, **kw):
            return "Ответ"

    shared_mod.OAI = _O()
    # keep stickers object but it no-ops
    shared_mod.STICKERS = _DummyStickers()

    msg = _FakeMsg()
    asyncio.run(shared_mod.handle_llm_request_shared(msg, "привет", reply_to_id=None))

    # exactly one text message
    assert len(fake_bot.sent) == 1
    assert fake_bot.sent[0][1] == "Ответ"


def test_handle_llm_main_ratelimit_branch(monkeypatch):
    class _DummyTyping:
        def __init__(self, *a, **kw):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(chat_action_mod.ChatActionSender, "typing", _DummyTyping)

    fake_bot = _FakeBot()
    shared_mod._bot = fake_bot
    shared_mod.STICKERS = _DummyStickers()
    monkeypatch.setattr(shared_mod.RATE, "allow", lambda uid, cid: True)

    calls = {"n": 0}
    class _O:
        def ask(self, *a, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                from openai import RateLimitError
                raise RateLimitError("rl")
            return "Подожди, лимиты"

    shared_mod.OAI = _O()
    msg = _FakeMsg()
    asyncio.run(shared_mod.handle_llm_request_shared(msg, "тест", reply_to_id=None))
    assert fake_bot.sent, "should produce a message on ratelimit"


def test_handle_llm_main_openai_error_branch(monkeypatch):
    class _DummyTyping:
        def __init__(self, *a, **kw):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(chat_action_mod.ChatActionSender, "typing", _DummyTyping)
    fake_bot = _FakeBot()
    shared_mod._bot = fake_bot
    shared_mod.STICKERS = _DummyStickers()
    monkeypatch.setattr(shared_mod.RATE, "allow", lambda uid, cid: True)

    calls = {"n": 0}
    class _O:
        def ask(self, *a, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                from openai import OpenAIError
                raise OpenAIError("boom")
            return "Модель легла"

    shared_mod.OAI = _O()
    asyncio.run(shared_mod.handle_llm_request_shared(_FakeMsg(), "тест", reply_to_id=None))
    assert fake_bot.sent, "should produce a message on openai error"


def test_handle_llm_main_unexpected_error_branch(monkeypatch):
    class _DummyTyping:
        def __init__(self, *a, **kw):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(chat_action_mod.ChatActionSender, "typing", _DummyTyping)
    fake_bot = _FakeBot()
    shared_mod._bot = fake_bot
    shared_mod.STICKERS = _DummyStickers()
    monkeypatch.setattr(shared_mod.RATE, "allow", lambda uid, cid: True)

    calls = {"n": 0}
    class _O:
        def ask(self, *a, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("x")
            return "Сбой, позже"

    shared_mod.OAI = _O()
    asyncio.run(shared_mod.handle_llm_request_shared(_FakeMsg(), "тест", reply_to_id=None))
    assert fake_bot.sent, "should produce a message on unexpected error"


def test_handle_llm_empty_answer_generates_error(monkeypatch):
    class _DummyTyping:
        def __init__(self, *a, **kw):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(chat_action_mod.ChatActionSender, "typing", _DummyTyping)
    fake_bot = _FakeBot()
    shared_mod._bot = fake_bot
    shared_mod.STICKERS = _DummyStickers()
    monkeypatch.setattr(shared_mod.RATE, "allow", lambda uid, cid: True)

    calls = {"n": 0}
    class _O:
        def ask(self, *a, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                return "  "  # empty
            return "Пусто"

    shared_mod.OAI = _O()
    asyncio.run(shared_mod.handle_llm_request_shared(_FakeMsg(), "тест", reply_to_id=None))
    assert fake_bot.sent, "should produce a generated error message on empty answer"


