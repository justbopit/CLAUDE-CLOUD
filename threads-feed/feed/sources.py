"""Входные данные ленты: профиль голоса владельца и банк реальных историй."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

BANNED_HEADING = "никогда не пишу"


@dataclass(frozen=True)
class Voice:
    text: str
    banned: tuple[str, ...]


@dataclass(frozen=True)
class Story:
    id: str
    text: str
    date: str = ""
    media: str = "text"


def load_voice(path: Path) -> Voice:
    """Читает voice.md. Пункты раздела «Никогда не пишу» идут в фильтр."""
    text = path.read_text(encoding="utf-8")
    banned: list[str] = []
    in_banned = False
    for line in text.splitlines():
        if line.startswith("#"):
            in_banned = BANNED_HEADING in line.lower()
            continue
        m = re.match(r"^\s*[-*]\s+(.+?)\s*$", line)
        if in_banned and m:
            banned.append(m.group(1).strip("«»\"'"))
    return Voice(text=text, banned=tuple(banned))


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
