from prometheus_client import Counter, Gauge, Histogram, start_http_server

REQUESTS = Counter("bot_requests_total", "Total incoming requests", ["type"])  # text, sticker, gif, reaction
RESPONSES = Counter("bot_responses_total", "Total responses sent", ["type"])  # text, sticker
ERRORS = Counter("bot_errors_total", "Total errors", ["kind"])  # openai, telegram, unexpected
RATE_LIMITED = Counter("bot_rate_limited_total", "Total rate-limited events")
LLM_LATENCY = Histogram("bot_llm_latency_seconds", "LLM response latency seconds")
ACTIVE_CHATS = Gauge("bot_active_chats", "Number of chats seen in the last window")


def start_metrics_server(port: int = 9000):
    start_http_server(port)



