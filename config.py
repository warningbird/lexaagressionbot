import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    bot_token: str
    openai_api_key: str
    openai_model: str

    # Tunables
    telegram_chunk_size: int = 4000
    max_user_prompt_chars: int = 2000
    idle_check_interval_sec: int = 300
    idle_threshold_hours: int = 14
    roast_probability: float = 0.1
    greet_suppress_hours: int = 12
    roast_cooldown_hours: int = 6
    # Stickers
    sticker_set_candidates: tuple[str, ...] = ("DreamTeamNagh", "DreamTeam_by_Ksundrpuh")
    sticker_every_nth_reply: int = 3
    # GIFs search disabled (bot only reacts to incoming GIFs with stickers)
    # Style/probabilities
    passive_probability: float = 0.2
    corp_probability: float = 0.2
    short_reply_probability: float = 0.3
    # Telegram
    avatar_photos_limit: int = 1
    # Rate limit
    per_user_window_sec: int = 5
    per_user_max_requests: int = 1
    per_chat_window_sec: int = 10
    per_chat_max_requests: int = 5
    # Feature flags
    enable_stickers: bool = True
    enable_roast: bool = True
    enable_idle_monitor: bool = True


def load_config() -> AppConfig:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"

    if not bot_token:
        raise RuntimeError("BOT_TOKEN is required. Set BOT_TOKEN in .env or environment.")
    if not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required. Set OPENAI_API_KEY in .env or environment.")

    cfg = AppConfig(
        bot_token=bot_token,
        openai_api_key=openai_api_key,
        openai_model=openai_model,
    )
    # optional external providers / flags
    object.__setattr__(cfg, "tenor_api_key", os.getenv("TENOR_API_KEY", "").strip() or None)
    object.__setattr__(cfg, "giphy_api_key", os.getenv("GIPHY_API_KEY", "").strip() or None)
    # booleans from env ("1", "true", "yes")
    def _env_bool(name: str, default: bool) -> bool:
        v = os.getenv(name)
        if v is None:
            return default
        return v.strip().lower() in {"1", "true", "yes", "on"}

    object.__setattr__(cfg, "enable_stickers", _env_bool("ENABLE_STICKERS", cfg.enable_stickers))
    object.__setattr__(cfg, "enable_roast", _env_bool("ENABLE_ROAST", cfg.enable_roast))
    object.__setattr__(cfg, "enable_idle_monitor", _env_bool("ENABLE_IDLE_MONITOR", cfg.enable_idle_monitor))
    # probabilities overrides
    def _env_float(name: str, default: float) -> float:
        v = os.getenv(name)
        if not v:
            return default
        try:
            return float(v)
        except Exception:
            return default

    object.__setattr__(cfg, "passive_probability", _env_float("PASSIVE_PROB", cfg.passive_probability))
    object.__setattr__(cfg, "corp_probability", _env_float("CORP_PROB", cfg.corp_probability))
    object.__setattr__(cfg, "short_reply_probability", _env_float("SHORT_PROB", cfg.short_reply_probability))
    object.__setattr__(cfg, "roast_probability", _env_float("ROAST_PROB", cfg.roast_probability))

    # Validate numeric ranges
    def _check_01(name: str, value: float):
        if not (0.0 <= value <= 1.0):
            raise RuntimeError(f"{name} must be between 0.0 and 1.0; got {value}")

    _check_01("PASSIVE_PROB", cfg.passive_probability)
    _check_01("CORP_PROB", cfg.corp_probability)
    _check_01("SHORT_PROB", cfg.short_reply_probability)
    _check_01("ROAST_PROB", cfg.roast_probability)
    if cfg.sticker_every_nth_reply < 1:
        raise RuntimeError("sticker_every_nth_reply must be >= 1")
    if cfg.idle_check_interval_sec < 1:
        raise RuntimeError("idle_check_interval_sec must be >= 1")
    if cfg.idle_threshold_hours < 1:
        raise RuntimeError("idle_threshold_hours must be >= 1")
    if cfg.greet_suppress_hours < 0:
        raise RuntimeError("greet_suppress_hours must be >= 0")
    if cfg.roast_cooldown_hours < 0:
        raise RuntimeError("roast_cooldown_hours must be >= 0")
    if cfg.telegram_chunk_size < 100:
        raise RuntimeError("telegram_chunk_size looks too small (<100)")
    if cfg.max_user_prompt_chars < 100:
        raise RuntimeError("max_user_prompt_chars looks too small (<100)")
    return cfg


