from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque


def login_rate_limit() -> int:
    try:
        return int(os.environ.get("FERLUNA_LOGIN_RATE_LIMIT", "10"))
    except ValueError:
        return 10


def login_rate_window_seconds() -> int:
    try:
        return int(os.environ.get("FERLUNA_LOGIN_RATE_WINDOW", "300"))
    except ValueError:
        return 300


_login_attempts_lock = threading.Lock()
_login_attempts: dict[str, deque[float]] = defaultdict(deque)


def login_rate_limited(client_id: str) -> bool:
    """Record a login attempt and report whether the client is over the limit."""
    limit = login_rate_limit()
    if limit <= 0:
        return False

    window = login_rate_window_seconds()
    now = time.monotonic()
    with _login_attempts_lock:
        attempts = _login_attempts[client_id]
        while attempts and now - attempts[0] > window:
            attempts.popleft()
        if len(attempts) >= limit:
            return True
        attempts.append(now)
        return False


def reset_login_attempts(client_id: str | None) -> None:
    if client_id is None:
        return
    with _login_attempts_lock:
        _login_attempts.pop(client_id, None)
