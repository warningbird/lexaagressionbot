# LexaAgressionAI

A toxic Telegram bot that replies in an aggressive, sarcastic style. Text-only responses via OpenAI Responses API.

## Requirements
- Python 3.11+ (3.13 recommended)
- Telegram bot token from BotFather
- OpenAI API access with active billing (text)

## Installation
```
git clone <repo_url>
cd LexaAgressionAI

python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration
Create a `.env` file in the project root:
```
BOT_TOKEN=8343590344:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
OPENAI_API_KEY=sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
# Optional:
# OPENAI_MODEL=gpt-4o-mini
# Feature flags:
# ENABLE_STICKERS=true
# ENABLE_ROAST=true
# ENABLE_IDLE_MONITOR=true
# Probabilities (0..1):
# PASSIVE_PROB=0.2
# CORP_PROB=0.2
# SHORT_PROB=0.3
# ROAST_PROB=0.1
```
- BOT_TOKEN — your bot token.
- OPENAI_API_KEY — from `https://platform.openai.com` (billing required).
- OPENAI_MODEL — default is `gpt-4o-mini`.

### Environment variables

| Name | Default | Description |
|------|---------|-------------|
| `BOT_TOKEN` | — | Telegram bot token (required) |
| `OPENAI_API_KEY` | — | OpenAI API key (required) |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model for responses |
| `ENABLE_STICKERS` | `true` | Send a sticker every Nth reply (see below) |
| `ENABLE_ROAST` | `true` | Enable optional avatar “roast” addendum |
| `ENABLE_IDLE_MONITOR` | `true` | Periodic idle reminders to chats |
| `PASSIVE_PROB` | `0.2` | Probability of passive style |
| `CORP_PROB` | `0.2` | Probability of corporate style |
| `SHORT_PROB` | `0.3` | Probability of short replies |
| `ROAST_PROB` | `0.1` | Probability to add avatar “roast” when avatar exists |

Internal tunables (config.py):
- Chunk size (`telegram_chunk_size`): 4000
- Greeting suppression (`greet_suppress_hours`): 12h
- Roast cooldown (`roast_cooldown_hours`): 6h
- Sticker cadence (`sticker_every_nth_reply`): 3

## Run
```
python main.py
```
Logs will show "Start polling" and OpenAI responses with status 200 OK (JSON logs). Stop with Ctrl+C.

## Usage
- Private chats: send any text — the bot replies. Slash commands are disabled.
- Groups:
  - Mention the bot `@username` — it will reply.
  - If you mention the bot while replying to a message (quote), the bot replies to the quoted text.
  - If you mention the bot on a forwarded message, it uses the forward's text/caption.
- Replies are sent as a reply to the trigger message. Long messages are chunked (~4000 chars each).

## Troubleshooting
- TelegramNotFound at startup:
  - Check BOT_TOKEN correctness (no extra characters).
- OpenAIError: api_key ...:
  - OPENAI_API_KEY missing or not loaded from .env.
- 429 insufficient_quota / RateLimitError:
  - Billing/quota exhausted. Top up in `https://platform.openai.com`.
- terminated by other getUpdates request:
  - Multiple instances running. Stop extra ones.


## Update dependencies
```
pip install -r requirements.txt --upgrade
```

## Production (optional)
- Run via systemd/pm2/supervisor. Use absolute path to `.venv/bin/python` and `main.py`, enable autorestart and log collection.

## Docker

### Quick start
1. Create `.env` next to `docker-compose.yml` with:
```
BOT_TOKEN=8343590344:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
OPENAI_API_KEY=sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
# Optional:
# OPENAI_MODEL=gpt-4o-mini
# Feature flags (optional): see above
```
2. Build and run:
```
docker compose up -d --build
```


### Stop/logs
```
docker compose logs -f
docker compose stop
docker compose down
```

## Observability
- Metrics: `http://localhost:9000/metrics` (Prometheus format)
- Health: `http://localhost:8080/healthz`

### Suggested alerts (PromQL)
- High LLM error rate: `sum(rate(bot_errors_total{kind=~"openai|unexpected"}[5m])) > 0.1`
- Rate-limited spikes: `rate(bot_rate_limited_total[5m]) > 1`
- Slow LLM latency p95: `histogram_quantile(0.95, sum(rate(bot_llm_latency_seconds_bucket[5m])) by (le)) > 5`

## Security
- Do not commit `.env` and keys to the repository.
- Use OpenAI Organization/Workspace with Usage Limits.
