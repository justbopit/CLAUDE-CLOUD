"""Лента t88: 6–8 своих постов в день голосом владельца, только из реальных историй."""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path

from . import ai_filter
from .gemini import Gemini, GeminiError
from .voice import STYLE_RULES, Voice

MIN_PER_DAY = 6
MAX_PER_DAY = 8
# Лишние истории на случай, если часть черновиков не пройдёт фильтр.
SPARE_STORIES = 2
DAY_START = time(9, 0)
DAY_END = time(22, 0)
JITTER_MINUTES = 20

SYSTEM_TEMPLATE = """\
Ты пишешь посты для Threads от первого лица голосом владельца аккаунта.
Ниже его профиль голоса: как он пишет, примеры его постов и чего он никогда не пишет.

Правила:
- Один пост строго по одной истории. Только факты из истории: не добавляй события,
  людей, цифры, даты и выводы, которых в ней нет. Если деталей мало, пиши короче.
- До 450 символов.
- Пост про текст и историю, никаких отсылок к видео.
{rules}

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
            },
        }
    },
    "required": ["posts"],
}


@dataclass(frozen=True)
class Story:
    id: str
    text: str
    date: str = ""
    media: str = "text"


@dataclass(frozen=True)
class Draft:
    story_id: str
    text: str


@dataclass
class Post:
    at: str
    story_id: str
    text: str


@dataclass
class Rejected:
    story_id: str
    text: str
    reasons: str


@dataclass
class DayPlan:
    day: str
    posts: list[Post] = field(default_factory=list)
    rejected: list[Rejected] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def load_stories(path: Path) -> list[Story]:
    """Читает stories.jsonl: одна реальная история на строку."""
    stories = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
            stories.append(
                Story(
                    id=str(raw["id"]),
                    text=raw["text"].strip(),
                    date=raw.get("date", ""),
                    media=raw.get("media", "text"),
                )
            )
        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            raise ValueError(f"{path}:{n}: битая история ({e})") from e
    return stories


def pick_stories(stories: list[Story], used: set[str], limit: int) -> list[Story]:
    """Свежие неиспользованные истории без видео, сначала новые."""
    fresh = [s for s in stories if s.id not in used and s.media != "video" and s.text]
    fresh.sort(key=lambda s: s.date, reverse=True)
    return fresh[:limit]


class FeedWriter:
    """Пишет посты через Gemini голосом владельца."""

    def __init__(self, gemini: Gemini, voice: Voice):
        self.gemini = gemini
        self.system = SYSTEM_TEMPLATE.format(rules=STYLE_RULES, voice=voice.text.strip())

    def draft(self, stories: list[Story]) -> list[Draft]:
        """Черновики: по одному посту на каждую историю."""
        listing = "\n\n".join(
            f'<story id="{s.id}" date="{s.date}">\n{s.text}\n</story>' for s in stories
        )
        data = self.gemini.ask(
            self.system,
            f"Напиши по одному посту на каждую историю. story_id бери из атрибута id.\n\n{listing}",
            POSTS_SCHEMA,
        )
        posts = data.get("posts")
        if not isinstance(posts, list):
            raise GeminiError("в ответе Gemini нет списка posts")
        known = {s.id for s in stories}
        # Пост без реальной истории за ним в ленту не идёт.
        return [
            Draft(p["story_id"], p["text"].strip())
            for p in posts
            if isinstance(p, dict)
            and p.get("story_id") in known
            and isinstance(p.get("text"), str)
        ]

    def rewrite(self, story: Story, text: str, issues: str) -> str:
        """Переписывает пост, который не прошёл фильтр, с перечнем замечаний."""
        return self.gemini.ask_text(
            self.system,
            "Этот пост выдаёт нейросеть или выходит за факты истории. "
            "Перепиши его голосом владельца, убрав все замечания.\n\n"
            f'<story id="{story.id}">\n{story.text}\n</story>\n\n'
            f"<draft>\n{text}\n</draft>\n\n<issues>\n{issues}\n</issues>",
        )


def schedule(day: date, count: int, seed: int | None = None) -> list[str]:
    """Равномерно раскладывает посты по дню с небольшим разбросом."""
    if count == 0:
        return []
    rng = random.Random(day.toordinal() if seed is None else seed)
    start = datetime.combine(day, DAY_START)
    step = (datetime.combine(day, DAY_END) - start) / count
    times = []
    for i in range(count):
        slot = start + step * i + step / 2
        slot += timedelta(minutes=rng.randint(-JITTER_MINUTES, JITTER_MINUTES))
        times.append(slot.strftime("%H:%M"))
    return times


def build_day(
    day: date,
    voice: Voice,
    stories: list[Story],
    used: set[str],
    writer: FeedWriter,
    per_day: int = 7,
    attempts: int = 2,
) -> DayPlan:
    per_day = max(MIN_PER_DAY, min(MAX_PER_DAY, per_day))
    plan = DayPlan(day=day.isoformat())
    chosen = pick_stories(stories, used, per_day + SPARE_STORIES)
    if not chosen:
        plan.warnings.append("нет свежих историй без видео: добавьте реальные истории в stories.jsonl")
        return plan

    by_id = {s.id: s for s in chosen}
    accepted: list[tuple[str, str]] = []
    seen: set[str] = set()
    for draft in writer.draft(chosen):
        if len(accepted) == per_day:
            break
        if draft.story_id in seen:
            continue
        seen.add(draft.story_id)
        story = by_id[draft.story_id]
        text, issues = ai_filter.polish(
            draft.text, story.text, voice.banned,
            lambda t, i: writer.rewrite(story, t, i), attempts,
        )
        if issues:
            plan.rejected.append(Rejected(story.id, text, issues))
        else:
            accepted.append((story.id, text))

    if len(accepted) < MIN_PER_DAY:
        plan.warnings.append(
            f"готово {len(accepted)} из минимум {MIN_PER_DAY} постов: "
            "не хватает историй или черновики не прошли фильтр, выдумывать не будем"
        )
    for at, (story_id, text) in zip(schedule(day, len(accepted)), accepted):
        plan.posts.append(Post(at, story_id, text))
    return plan
