"""HTTP на stdlib: JSON-запросы к Gemini и Threads API без внешних зависимостей."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

RETRY_STATUSES = {429, 500, 502, 503, 504}


class HTTPError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status


def request_json(
    method: str,
    url: str,
    *,
    params: dict | None = None,
    body: dict | None = None,
    headers: dict | None = None,
    timeout: float = 120,
    retries: int = 2,
    sleep=time.sleep,
) -> dict:
    """Отправляет запрос и возвращает JSON ответа.

    429 и 5xx повторяются до `retries` раз с паузой 2, 4, ... секунды.
    В текст ошибки идёт только сообщение API: URL с токеном в логи не попадает.
    """
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json; charset=utf-8")
    for name, value in (headers or {}).items():
        req.add_header(name, value)

    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            if e.code in RETRY_STATUSES and attempt < retries:
                sleep(2 ** (attempt + 1))
                continue
            raise HTTPError(e.code, _error_message(e)) from None
    raise AssertionError("unreachable")


def _error_message(e: urllib.error.HTTPError) -> str:
    raw = e.read().decode(errors="replace")
    try:
        err = json.loads(raw).get("error", {})
        return err.get("message") or raw[:300]
    except (json.JSONDecodeError, AttributeError):
        return raw[:300] or e.reason
