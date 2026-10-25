"""Фильтр AI-признаков: ловит штампы, по которым текст выдаёт нейросеть.

Проверки детерминированные, без вызова модели, чтобы фильтр был дешёвым
и предсказуемым. Жёсткое срабатывание отклоняет пост сразу, мягкие
отклоняют, только если их набралось MAX_SOFT_HITS или больше.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

THREADS_CHAR_LIMIT = 500
MAX_SOFT_HITS = 2

# Фразы-штампы. Регулярки на нижнем регистре, ё заменена на е.
HARD_PHRASES = {
    "давайте разберемся": r"\bдавайте\s+разбер[её]мся\b",
    "в современном мире": r"\bв\s+современном\s+мире\b",
    "важно отметить": r"\b(важно|стоит)\s+отметить\b",
    "не просто X, а Y": r"\bне\s+просто\b[^.!?\n]{1,60}?,\s*а\b",
    "это не про X, это про Y": r"\bэто\s+не\s+про\b[^.!?\n]{1,60}?\bэто\s+про\b",
    "погрузимся": r"\bпогруз(имся|иться|ись)\b",
    "в заключение": r"\bв\s+заключени[еи]\b",
    "раскрыть потенциал": r"\bраскры\w*\s+(свой\s+|ваш\s+)?потенциал",
    "представьте себе": r"\bпредставьте\s+(себе|только)\b",
    "секрет в том": r"\bсекрет\s+(прост|в\s+том)\b",
    "поделитесь в комментариях": r"\bподелитесь\b.{0,30}\bкомментари",
    "а вы как думаете": r"\bа\s+(вы|ты)\s+(как\s+думаете|что\s+думаете|согласны)\b",
    "как ИИ": r"\bкак\s+(ии|искусственный\s+интеллект|языковая\s+модель)\b",
    "delve": r"\bdelv(e|ing)\b",
    "tapestry": r"\btapestry\b",
    "game-changer": r"\bgame[\s-]?changer\b",
    "in today's world": r"\bin\s+today'?s\s+(world|fast)",
    "as an AI": r"\bas\s+an\s+ai\b",
}

SOFT_PHRASES = {
    "итак": r"(^|[.!?]\s+)итак\b",
    "ключевой": r"\bключев(ой|ая|ое|ые|ого)\b",
    "уникальный": r"\bуникальн\w*",
    "путешествие": r"\bпутешестви[ея]\s+(к|в\s+мир)\b",
    "революционный": r"\bреволюционн\w*",
    "друзья,": r"(^|\n)\s*друзья\s*[,!]",
    "вот почему": r"\bвот\s+почему\b",
    "по сути": r"\bпо\s+сути\b",
    "однозначно": r"\bоднозначно\b",
    "инсайт": r"\bинсайт\w*",
}

EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]"
)
LIST_LINE_RE = re.compile(r"^\s*(?:[-•*▪✅]|\d+[.)])\s+", re.MULTILINE)


@dataclass(frozen=True)
class Hit:
    rule: str
    severity: str  # "hard" | "soft"
    snippet: str = ""


@dataclass
class Verdict:
    hits: list[Hit] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        hard = [h for h in self.hits if h.severity == "hard"]
        soft = [h for h in self.hits if h.severity == "soft"]
        return not hard and len(soft) < MAX_SOFT_HITS

    def feedback(self) -> str:
        """Человекочитаемый список замечаний для переписывания."""
        return "\n".join(
            f"- {h.rule}" + (f": «{h.snippet}»" if h.snippet else "")
            for h in self.hits
        )


def _normalize(text: str) -> str:
    return text.lower().replace("ё", "е")


def check(text: str, extra_banned: list[str] | tuple[str, ...] = ()) -> Verdict:
    """Проверяет пост и возвращает все сработавшие признаки."""
    verdict = Verdict()
    norm = _normalize(text)

    for rule, pattern in HARD_PHRASES.items():
        m = re.search(pattern, norm)
        if m:
            verdict.hits.append(Hit(rule, "hard", m.group(0).strip()))
    for rule, pattern in SOFT_PHRASES.items():
        m = re.search(pattern, norm, re.MULTILINE)
        if m:
            verdict.hits.append(Hit(rule, "soft", m.group(0).strip()))
    for phrase in extra_banned:
        if phrase and _normalize(phrase) in norm:
            verdict.hits.append(Hit("запрещено в профиле голоса", "hard", phrase))

    if "—" in text:
        verdict.hits.append(Hit("длинное тире", "hard", "—"))
    if len(text) > THREADS_CHAR_LIMIT:
        verdict.hits.append(
            Hit("длиннее лимита Threads", "hard", f"{len(text)} > {THREADS_CHAR_LIMIT}")
        )
    if "**" in text or "__" in text or re.search(r"^#+\s", text, re.MULTILINE):
        verdict.hits.append(Hit("markdown-разметка", "hard"))
    if len(LIST_LINE_RE.findall(text)) >= 2:
        verdict.hits.append(Hit("пост списком", "hard"))

    emoji = len(EMOJI_RE.findall(text))
    if emoji > 2:
        verdict.hits.append(Hit("много эмодзи", "hard", str(emoji)))
    hashtags = len(re.findall(r"(?<!\w)#\w+", text))
    if hashtags > 1:
        verdict.hits.append(Hit("больше одного хэштега", "hard", str(hashtags)))
    if text.count("!") > 1:
        verdict.hits.append(Hit("много восклицаний", "soft", str(text.count("!"))))
    if re.match(r"^[^.!?\n]{3,80}\?\s", text.strip()):
        verdict.hits.append(Hit("риторический вопрос в начале", "soft"))

    return verdict


_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")


def invented_numbers(post: str, story: str) -> list[str]:
    """Числа из поста, которых нет в исходной истории.

    Цифры в посте должны браться из реальной истории; придуманные суммы,
    сроки и проценты выдают выдумку быстрее всего.
    """
    source = {n.replace(",", ".") for n in _NUMBER_RE.findall(story)}
    return [
        n for n in _NUMBER_RE.findall(post) if n.replace(",", ".") not in source
    ]
