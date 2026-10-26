"""Профиль голоса владельца: voice.md, заполненный по памяти fukkality-threads-voice."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

BANNED_HEADING = "никогда не пишу"

# Общие правила письма для ленты и для ответов лидам.
STYLE_RULES = """\
- Подражай ритму, словарю и длине фраз из примеров владельца, а не своему привычному стилю.
- Обычный текст: без markdown, без списков, без хэштегов, максимум одно эмодзи
  и только если оно есть в примерах владельца.
- Без длинного тире «—» и без штампов вроде «давайте разберёмся», «важно отметить»,
  «не просто X, а Y», «в мире, где», «и знаете что».
- Без призывов «поделитесь в комментариях» и вопросов к аудитории в конце."""


@dataclass(frozen=True)
class Voice:
    text: str
    banned: tuple[str, ...]


def load_voice(path: Path) -> Voice:
    """Читает voice.md. Пункты раздела «Никогда не пишу» идут в фильтр AI-признаков."""
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
