import time


class RateLimiter:
    def __init__(self, per_user_window_sec: int, per_user_max: int, per_chat_window_sec: int, per_chat_max: int):
        self.per_user_window_sec = per_user_window_sec
        self.per_user_max = per_user_max
        self.per_chat_window_sec = per_chat_window_sec
        self.per_chat_max = per_chat_max
        self._user_times: dict[int, list[float]] = {}
        self._chat_times: dict[int, list[float]] = {}

    def allow(self, user_id: int, chat_id: int) -> bool:
        now = time.monotonic()
        # user
        utimes = self._user_times.setdefault(user_id, [])
        cutoff_u = now - self.per_user_window_sec
        self._user_times[user_id] = [t for t in utimes if t >= cutoff_u]
        if len(self._user_times[user_id]) >= self.per_user_max:
            return False

        # chat
        ctimes = self._chat_times.setdefault(chat_id, [])
        cutoff_c = now - self.per_chat_window_sec
        self._chat_times[chat_id] = [t for t in ctimes if t >= cutoff_c]
        if len(self._chat_times[chat_id]) >= self.per_chat_max:
            return False

        self._user_times[user_id].append(now)
        self._chat_times[chat_id].append(now)
        return True


