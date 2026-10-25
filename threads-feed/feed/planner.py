"""Дневной план ленты: 6–8 своих постов, каждый прошёл фильтр AI-признаков."""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta

from . import ai_filter
from .generator import Generator
from .sources import Story, Voice, pick_stories

MIN_PER_DAY = 6
MAX_PER_DAY = 8
# Лишние истории на случай, если часть черновиков не пройдёт фильтр.
SPARE_STORIES = 2
DAY_START = time(9, 0)
DAY_END = time(22, 0)
JITTER_MINUTES = 20


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


def problems(text: str, story: Story, voice: Voice) -> str:
    """Все замечания к посту одной строкой; пусто, если пост годен."""
    verdict = ai_filter.check(text, voice.banned)
    issues = verdict.feedback() if not verdict.passed else ""
    invented = ai_filter.invented_numbers(text, story.text)
    if invented:
        extra = f"- числа, которых нет в истории: {', '.join(invented)}"
        issues = f"{issues}\n{extra}" if issues else extra
    return issues


def schedule(day: date, count: int, seed: int | None = None) -> list[str]:
    """Равномерно раскладывает посты по дню с небольшим разбросом."""
    if count == 0:
        return []
    rng = random.Random(day.toordinal() if seed is None else seed)
    start = datetime.combine(day, DAY_START)
    span = datetime.combine(day, DAY_END) - start
    step = span / count
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
    generator: Generator,
    per_day: int = 7,
    max_attempts: int = 2,
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
    for draft in generator.draft(chosen):
        if len(accepted) == per_day:
            break
        if draft.story_id in seen:
            continue
        seen.add(draft.story_id)
        story = by_id[draft.story_id]
        text = draft.text
        issues = problems(text, story, voice)
        for _ in range(max_attempts - 1):
            if not issues:
                break
            text = generator.rewrite(story, text, issues)
            issues = problems(text, story, voice)
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
