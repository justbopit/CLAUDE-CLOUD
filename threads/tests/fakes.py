"""Фейковые Gemini и Threads: тесты не ходят в сеть."""

import json

from threadskit.gemini import Gemini
from threadskit.threads_api import ThreadsAPI


def gemini_response(payload) -> dict:
    return {
        "candidates": [{
            "content": {"parts": [{"text": json.dumps(payload, ensure_ascii=False)}]},
            "finishReason": "STOP",
        }]
    }


def fake_gemini(*payloads):
    """Gemini, который по очереди отдаёт заготовленные JSON-ответы.

    Готовый сырой ответ API (с candidates или promptFeedback) отдаётся как есть.
    """
    calls = []
    queue = list(payloads)

    def post(url, body, headers):
        calls.append({"url": url, "body": body, "headers": headers})
        item = queue.pop(0)
        if isinstance(item, dict) and ("candidates" in item or "promptFeedback" in item):
            return item
        return gemini_response(item)

    return Gemini("test-key", post=post), calls


def prompt_of(call) -> str:
    return call["body"]["contents"][0]["parts"][0]["text"]


def fake_threads(search_results=None, statuses=("FINISHED",)):
    """Threads API: поиск отдаёт посты по запросу, публикация проходит по шагам."""
    calls = []
    statuses = list(statuses)

    def request(method, url, params=None, retries=2):
        calls.append({"method": method, "url": url, "params": params, "retries": retries})
        path = url.rsplit("/v1.0/", 1)[1]
        if path == "keyword_search":
            return {"data": (search_results or {}).get(params["q"], [])}
        if path == "me/threads":
            return {"id": "container-1"}
        if path == "me/threads_publish":
            return {"id": "reply-1"}
        return {"status": statuses.pop(0) if statuses else "IN_PROGRESS"}

    return ThreadsAPI("test-token", request=request, sleep=lambda _: None), calls
