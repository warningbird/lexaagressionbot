import logging
import time
from collections.abc import Sequence

from openai import OpenAI, OpenAIError, RateLimitError

from config import load_config

CFG = load_config()


class OpenAIService:
    def __init__(self, client: OpenAI | None = None):
        self.client = client or OpenAI(api_key=CFG.openai_api_key)

    def ask(self, messages: Sequence[dict], model: str | None = None, *, timeout_sec: float = 30.0,
            max_retries: int = 3, backoff_base: float = 0.6) -> str:
        system_prompt = None
        user_texts: list[str] = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                system_prompt = content
            elif role == "user":
                user_texts.append(str(content))
        user_input = "\n\n".join(user_texts) if user_texts else ""

        use_model = (model or CFG.openai_model)

        last_exc: Exception | None = None
        for attempt in range(1, max_retries + 1):
            start = time.monotonic()
            try:
                resp = self.client.responses.create(
                    model=use_model,
                    instructions=system_prompt,
                    input=user_input,
                    timeout=timeout_sec,
                )
                return resp.output_text
            except RateLimitError as e:
                last_exc = e
                logging.warning("OpenAI rate limit on attempt %d/%d: %s", attempt, max_retries, str(e)[:200])
            except OpenAIError as e:
                last_exc = e
                logging.warning("OpenAI SDK error on attempt %d/%d: %s", attempt, max_retries, str(e)[:200])
            except Exception as e:
                last_exc = e
                logging.warning("OpenAI unexpected error on attempt %d/%d: %s", attempt, max_retries, str(e)[:200])
            finally:
                elapsed = time.monotonic() - start
                if elapsed > timeout_sec:
                    logging.info("OpenAI call exceeded timeout: %.2fs", elapsed)

            if attempt < max_retries:
                sleep_s = backoff_base * (2 ** (attempt - 1))
                time.sleep(sleep_s)

        if last_exc:
            raise last_exc
        return ""


