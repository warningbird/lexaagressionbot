import asyncio
import os
from types import SimpleNamespace

os.environ.setdefault("BOT_TOKEN", "TEST_TOKEN")
os.environ.setdefault("OPENAI_API_KEY", "TEST_OPENAI_API_KEY")

from bot.routers import groups


def test_poll_options_build_variative(monkeypatch):
    # monkeypatch _OAI.ask to return deterministic texts for different prompts
    seq = iter([
        "идём, наконец-то",           # intro
        "шмель сегодня или слабо?",  # question
        "ради атмосферы",            # tail_yes
        "денег нет",                 # tail_no
    ])

    async def fake_to_thread(fn, *a, **kw):
        return next(seq)

    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)

    tail_yes = "ради атмосферы"
    tail_no = "денег нет"
    opt_yes = f"иду — {tail_yes}" if tail_yes else "иду"
    opt_no = f"не иду — {tail_no}" if tail_no else "не иду"
    assert "иду" in opt_yes.lower() and "не иду" in opt_no.lower()
    assert "—" in opt_yes and "—" in opt_no


class _FakeBot:
    def __init__(self):
        self._me = SimpleNamespace(username="lexa_bot")
        self.sent = []
        self.polls = []

    async def get_me(self):
        return self._me

    async def send_message(self, chat_id: int, text: str, reply_to_message_id: int | None = None):
        self.sent.append((chat_id, text))
        return SimpleNamespace(message_id=len(self.sent))

    async def send_poll(self, chat_id: int, question: str, options: list[str], is_anonymous: bool, allows_multiple_answers: bool):
        self.polls.append((chat_id, question, options))
        return SimpleNamespace(message_id=100)


def _make_msg(text: str):
    # build a message that @mentions bot
    mention = "@lexa_bot"
    entities = [SimpleNamespace(type="mention", offset=0, length=len(mention))]
    chat = SimpleNamespace(id=1, type="group")
    from_user = SimpleNamespace(is_bot=False)
    return SimpleNamespace(text=f"{mention} {text}", entities=entities, chat=chat, from_user=from_user, reply_to_message=None, caption=None, message_id=42)


def test_group_trigger_creates_poll(monkeypatch):
    fake_bot = _FakeBot()

    # make LLM deterministic
    seq = iter(["intro", "вопрос?", "да", "нет"])
    async def fake_to_thread(fn, *a, **kw):
        return next(seq)
    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)

    m = _make_msg("идём в шмель?")
    asyncio.run(groups.group_trigger(m, fake_bot))
    assert fake_bot.polls, "poll should be created"
    assert any("иду" in opt.lower() for opt in fake_bot.polls[0][2])
    assert any("не иду" in opt.lower() for opt in fake_bot.polls[0][2])


def test_group_trigger_skips_if_already_polled_today(monkeypatch):
    fake_bot = _FakeBot()
    # mark polled today
    groups._last_poll_on_date[1] = "2099-01-01"
    # monkeypatch date to same key
    class _Z:
        def __init__(self, *a, **kw):
            pass
    monkeypatch.setattr(groups, "ZoneInfo", lambda *a, **kw: _Z())
    monkeypatch.setattr(groups, "datetime", SimpleNamespace(now=lambda tz=None: SimpleNamespace(date=lambda : SimpleNamespace(isoformat=lambda : "2099-01-01"))))

    m = _make_msg("шмель")
    asyncio.run(groups.group_trigger(m, fake_bot))
    assert fake_bot.sent, "should send 'already voted' message"


