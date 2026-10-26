"""Клиент Gemini: один запрос generateContent, ответ строго по JSON-схеме."""

from __future__ import annotations

import json
import os

from . import net

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# Стабильная модель с 2026-09-02; семейство 2.5 выведено из API 2026-10-20.
DEFAULT_MODEL = "gemini-3.8-flash"

TEXT_SCHEMA = {
    "type": "object",
    "properties": {"text": {"type": "string"}},
    "required": ["text"],
}


class GeminiError(RuntimeError):
    pass


class Gemini:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, post=None):
        self.api_key = api_key
        self.model = model
        self._post = post or (lambda url, body, headers: net.request_json(
            "POST", url, body=body, headers=headers))

    @classmethod
    def from_env(cls) -> "Gemini":
        """Ключ из GEMINI_API_KEY (или GOOGLE_API_KEY), модель из GEMINI_MODEL."""
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise GeminiError("нет ключа: задайте GEMINI_API_KEY")
        return cls(key, os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL)

    def ask(self, system: str, prompt: str, schema: dict) -> dict:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
            },
        }
        try:
            data = self._post(API_URL.format(model=self.model), body,
                              {"x-goog-api-key": self.api_key})
        except net.HTTPError as e:
            raise GeminiError(f"Gemini: {e}") from None

        block = (data.get("promptFeedback") or {}).get("blockReason")
        if block:
            raise GeminiError(f"Gemini заблокировал запрос: {block}")
        candidates = data.get("candidates") or []
        if not candidates:
            raise GeminiError("в ответе Gemini нет кандидатов")
        candidate = candidates[0]
        finish = candidate.get("finishReason", "STOP")
        if finish != "STOP":
            raise GeminiError(f"Gemini оборвал ответ: {finish}")
        parts = (candidate.get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        try:
            result = json.loads(text)
        except json.JSONDecodeError as e:
            raise GeminiError(f"Gemini вернул не JSON: {e}") from None
        if not isinstance(result, dict):
            raise GeminiError("Gemini вернул JSON не того вида")
        return result

    def ask_text(self, system: str, prompt: str) -> str:
        text = self.ask(system, prompt, TEXT_SCHEMA).get("text")
        if not isinstance(text, str):
            raise GeminiError("в ответе Gemini нет поля text")
        return text.strip()
