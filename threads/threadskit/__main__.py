"""Запуск:
    python -m threadskit feed --date 2026-10-26 --per-day 7   лента t88 на день
    python -m threadskit radar                                 радар LEADS (t82)
    python -m threadskit reply 3                               ответить лиду №3
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

from . import feed, radar
from .gemini import Gemini, GeminiError
from .threads_api import ThreadsAPI, ThreadsError
from .voice import load_voice

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
STATE = ROOT / "state"


def _read_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run_feed(args) -> int:
    voice = load_voice(args.voice)
    stories = feed.load_stories(args.stories)
    used_path = STATE / "used.json"
    used = set(_read_json(used_path, []))

    writer = feed.FeedWriter(Gemini.from_env(), voice)
    plan = feed.build_day(args.date, voice, stories, used, writer, per_day=args.per_day)

    out_file = OUT / f"feed-{plan.day}.json"
    _write_json(out_file, plan.to_dict())
    # Историю отмечаем использованной, только когда пост по ней попал в план.
    _write_json(used_path, sorted(used | {post.story_id for post in plan.posts}))

    print(f"{out_file}: {len(plan.posts)} постов, отклонено {len(plan.rejected)}")
    for w in plan.warnings:
        print(f"внимание: {w}", file=sys.stderr)
    return 0


def run_radar(args) -> int:
    config = radar.load_config(args.config)
    voice = load_voice(args.voice)
    now = datetime.now().astimezone()
    seen_path = STATE / "radar_seen.json"
    seen = _read_json(seen_path, {})

    writer = radar.LeadWriter(Gemini.from_env(), voice, config)
    report = radar.scan(config, voice, ThreadsAPI.from_env(), writer, seen, now)

    book = radar.LeadBook(STATE / "leads.json")
    book.add(report.leads)
    book.save()
    _write_json(seen_path, radar.remember(seen, report.judged, now))

    out_file = OUT / f"radar-{now:%Y-%m-%d-%H%M%S}.md"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(radar.render(report, config), encoding="utf-8")
    print(f"{out_file}: новых постов {report.scanned}, лидов {len(report.leads)}")
    for lead in report.leads:
        print(f"  {lead.n}. @{lead.username} {lead.score}/100: {lead.why}")
    for w in report.warnings:
        print(f"внимание: {w}", file=sys.stderr)
    return 0


def run_reply(args) -> int:
    book = radar.LeadBook(STATE / "leads.json")
    lead = book.find(args.lead)
    if lead is None:
        print(f"лид {args.lead} не найден, смотрите номера в out/radar-*.md", file=sys.stderr)
        return 1
    if lead.replied:
        print(f"лиду {lead.n} (@{lead.username}) уже ответили", file=sys.stderr)
        return 1
    text = (args.text or lead.reply).strip()
    if not text:
        print(f"у лида {lead.n} нет готового ответа, передайте свой через --text", file=sys.stderr)
        return 1

    print(f"@{lead.username}: {text}")
    if args.dry_run:
        return 0
    reply_id = ThreadsAPI.from_env().reply(lead.id, text)
    lead.reply, lead.replied = text, True
    book.save()
    print(f"ответ опубликован: {reply_id}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="threadskit", description="Threads голосом владельца")
    p.add_argument("--voice", type=Path, default=ROOT / "voice.md")
    sub = p.add_subparsers(dest="command", required=True)

    f = sub.add_parser("feed", help="лента на день: 6–8 своих постов из реальных историй")
    f.add_argument("--date", type=date.fromisoformat, default=date.today())
    f.add_argument("--per-day", type=int, default=7,
                   help=f"{feed.MIN_PER_DAY}–{feed.MAX_PER_DAY}")
    f.add_argument("--stories", type=Path, default=ROOT / "stories.jsonl")
    f.set_defaults(run=run_feed)

    r = sub.add_parser("radar", help="радар LEADS: кто в Threads ищет то, что делает владелец")
    r.add_argument("--config", type=Path, default=ROOT / "radar.json")
    r.set_defaults(run=run_radar)

    a = sub.add_parser("reply", help="ответить лиду из дайджеста радара в одно касание")
    a.add_argument("lead", help="номер лида из дайджеста или id поста")
    a.add_argument("--text", help="свой текст вместо черновика")
    a.add_argument("--dry-run", action="store_true", help="показать ответ, не отправляя")
    a.set_defaults(run=run_reply)

    args = p.parse_args(argv)
    try:
        return args.run(args)
    except (GeminiError, ThreadsError, ValueError, OSError) as e:
        print(f"ошибка: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
