"""Генерация текстов постов через Claude по реальным историям владельца."""

from __future__ import annotations

import json
from dataclasses import dataclass

from .sources import Story, Voice

MODEL = "claude-opus-5-5"
EFFORT = "medium"
MAX_TOKENS = 16000
# Отказ модели перезапускается на рекомендованной запасной модели на стороне API.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

SYSTEM_TEMPLATE = """\
Ты пишешь посты для Threads от первого лица голосом владельца аккаунта.
Ниже его профиль голоса: как он пишет, примеры его постов и чего он никогда не пишет.
Подражай ритму, словарю и длине фраз из примеров, а не своему привычному стилю.

Правила:
- Один пост строго по одной истории. Только факты из истории: не добавляй события,
  людей, цифры, даты и выводы, которых в ней нет. Если деталей мало, пиши короче.
- До 450 символов. Обычный текст: без markdown, без списков, без хэштегов,
  максимум одно эмодзи и только если оно есть в примерах владельца.
- Без длинного тире «—», без штампов вроде «давайте разберёмся», «важно отметить»,
  «не просто X, а Y», без призывов «поделитесь в комментариях» и вопросов к аудитории в конце.
- Пост про текст и историю, никаких отсылок к видео.

<voice>
{voice}
</voice>
"""

POSTS_SCHEMA = {
    "type": "object",
    "properties": {
        "posts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "story_id": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["story_id", "text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["posts"],
    "additionalProperties": False,
}

REWRITE_SCHEMA = {
    "type": "object",
    "properties": {"text": {"type": "string"}},
    "required": ["text"],
    "additionalProperties": False,
}


class GenerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Draft:
    story_id: str
    text: str


def make_client():
    """Клиент Anthropic; ключ берётся из ANTHROPIC_API_KEY или профиля `ant auth login`."""
    import anthropic

    return anthropic.Anthropic()


class Generator:
    def __init__(self, client, voice: Voice, model: str = MODEL):
        self.client = client
        self.voice = voice
        self.model = model
        self.system = SYSTEM_TEMPLATE.format(voice=voice.text.strip())

    def _ask(self, prompt: str, schema: dict) -> dict:
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            output_config={
                "effort": EFFORT,
                "format": {"type": "json_schema", "schema": schema},
            },
            system=self.system,
            messages=[{"role": "user", "content": prompt}],
        )
        if response.stop_reason == "refusal":
            raise GenerationError("Claude отказался писать пост")
        if response.stop_reason == "max_tokens":
            raise GenerationError("ответ Claude обрезан по max_tokens")
        text = next((b.text for b in response.content if b.type == "text"), None)
        if text is None:
            raise GenerationError("в ответе Claude нет текста")
        return json.loads(text)

    def draft(self, stories: list[Story]) -> list[Draft]:
        """Черновики: по одному посту на каждую историю."""
        listing = "\n\n".join(
            f'<story id="{s.id}" date="{s.date}">\n{s.text}\n</story>' for s in stories
        )
        data = self._ask(
            f"Напиши по одному посту на каждую историю. story_id бери из атрибута id.\n\n{listing}",
            POSTS_SCHEMA,
        )
        known = {s.id for s in stories}
        # Пост без реальной истории за ним в ленту не идёт.
        return [
            Draft(p["story_id"], p["text"].strip())
            for p in data["posts"]
            if p["story_id"] in known
        ]

    def rewrite(self, story: Story, text: str, feedback: str) -> str:
        """Переписывает пост, который не прошёл фильтр, с перечнем замечаний."""
        data = self._ask(
            "Этот пост выдаёт нейросеть или выходит за факты истории. "
            "Перепиши его голосом владельца, убрав все замечания.\n\n"
            f'<story id="{story.id}">\n{story.text}\n</story>\n\n'
            f"<draft>\n{text}\n</draft>\n\n<issues>\n{feedback}\n</issues>",
            REWRITE_SCHEMA,
        )
        return data["text"].strip()
