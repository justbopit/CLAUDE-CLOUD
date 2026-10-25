"""Запуск: python -m feed --date 2026-10-25 --per-day 7"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from .generator import Generator, GenerationError, make_client
from .planner import MAX_PER_DAY, MIN_PER_DAY, build_day
from .sources import load_stories, load_voice

ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="feed", description="Лента Threads голосом владельца")
    p.add_argument("--date", type=date.fromisoformat, default=date.today())
    p.add_argument("--per-day", type=int, default=7, help=f"{MIN_PER_DAY}–{MAX_PER_DAY}")
    p.add_argument("--voice", type=Path, default=ROOT / "voice.md")
    p.add_argument("--stories", type=Path, default=ROOT / "stories.jsonl")
    p.add_argument("--out", type=Path, default=ROOT / "out")
    p.add_argument("--used", type=Path, default=ROOT / "state" / "used.json")
    args = p.parse_args(argv)

    voice = load_voice(args.voice)
    stories = load_stories(args.stories)
    used = set(json.loads(args.used.read_text())) if args.used.exists() else set()

    try:
        plan = build_day(args.date, voice, stories, used, Generator(make_client(), voice),
                         per_day=args.per_day)
    except GenerationError as e:
        print(f"ошибка генерации: {e}", file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    out_file = args.out / f"{plan.day}.json"
    out_file.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    # Историю отмечаем использованной, только когда пост по ней попал в план.
    used |= {post.story_id for post in plan.posts}
    args.used.parent.mkdir(parents=True, exist_ok=True)
    args.used.write_text(json.dumps(sorted(used), ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{out_file}: {len(plan.posts)} постов, отклонено {len(plan.rejected)}")
    for w in plan.warnings:
        print(f"внимание: {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
