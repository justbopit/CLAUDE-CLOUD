"""Threads API: поиск свежих постов по ключевым словам и публикация ответа."""

from __future__ import annotations

import os
import time
from datetime import datetime

from . import net

GRAPH = "https://graph.threads.net/v1.0"
SEARCH_FIELDS = "id,text,media_type,permalink,timestamp,username"
SEARCH_LIMIT = 100
# Контейнер ответа обрабатывается не мгновенно: ждём FINISHED перед публикацией.
STATUS_POLLS = 10
STATUS_PAUSE = 3


class ThreadsError(RuntimeError):
    pass


class ThreadsAPI:
    def __init__(self, token: str, request=None, sleep=time.sleep):
        self.token = token
        self._request = request or net.request_json
        self._sleep = sleep

    @classmethod
    def from_env(cls) -> "ThreadsAPI":
        """Токен из THREADS_ACCESS_TOKEN: права threads_basic, threads_keyword_search,
        threads_content_publish и threads_manage_replies."""
        token = os.environ.get("THREADS_ACCESS_TOKEN")
        if not token:
            raise ThreadsError("нет токена: задайте THREADS_ACCESS_TOKEN")
        return cls(token)

    def _call(self, method: str, path: str, retries: int = 2, **params) -> dict:
        params["access_token"] = self.token
        try:
            return self._request(method, f"{GRAPH}/{path}", params=params, retries=retries)
        except net.HTTPError as e:
            raise ThreadsError(f"Threads: {e}") from None

    def search(self, query: str, since: datetime) -> list[dict]:
        """Свежие публичные посты по запросу, новые первыми."""
        data = self._call(
            "GET", "keyword_search",
            q=query, search_type="RECENT", fields=SEARCH_FIELDS,
            limit=SEARCH_LIMIT, since=int(since.timestamp()),
        )
        return [p for p in data.get("data", []) if isinstance(p, dict)]

    def reply(self, reply_to_id: str, text: str) -> str:
        """Публикует текстовый ответ на пост и возвращает id ответа."""
        container = self._call(
            "POST", "me/threads", media_type="TEXT", text=text, reply_to_id=reply_to_id,
        )["id"]
        for _ in range(STATUS_POLLS):
            state = self._call("GET", container, fields="status,error_message")
            status = state.get("status")
            if status == "FINISHED":
                break
            if status in ("ERROR", "EXPIRED"):
                raise ThreadsError(f"Threads не принял ответ: {state.get('error_message') or status}")
            self._sleep(STATUS_PAUSE)
        else:
            raise ThreadsError("Threads слишком долго готовит ответ, попробуйте ещё раз")
        # Публикацию не повторяем: после сбоя на стороне Threads ответ мог уже выйти.
        return self._call("POST", "me/threads_publish", retries=0, creation_id=container)["id"]
