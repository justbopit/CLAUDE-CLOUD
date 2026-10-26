import tempfile
import unittest
from datetime import date
from pathlib import Path

from threadskit.feed import (
    MAX_PER_DAY, FeedWriter, Story, build_day, load_stories, pick_stories, schedule,
)
from threadskit.gemini import GeminiError
from threadskit.voice import Voice, load_voice

from .fakes import fake_gemini, prompt_of

VOICE = Voice(text="Пишу коротко.", banned=("всем привет",))
DAY = date(2026, 10, 26)


def stories(n):
    return [Story(f"s{i}", f"История номер {i}: клиент молчал.", f"2026-10-{10 + i:02d}") for i in range(n)]


def build(items, *payloads, per_day=7):
    gemini, calls = fake_gemini(*payloads)
    return build_day(DAY, VOICE, items, set(), FeedWriter(gemini, VOICE), per_day=per_day), calls


class SourcesTest(unittest.TestCase):
    def test_voice_banned_section(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "voice.md"
            path.write_text("# Голос\n- коротко\n## Никогда не пишу\n- всем привет\n- «мотивация»\n", encoding="utf-8")
            self.assertEqual(load_voice(path).banned, ("всем привет", "мотивация"))

    def test_load_stories_and_skip_video(self):
        example = Path(__file__).resolve().parent.parent / "stories.example.jsonl"
        loaded = load_stories(example)
        self.assertEqual([s.id for s in pick_stories(loaded, set(), 5)], ["2026-10-20-client"])

    def test_broken_story_line(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "stories.jsonl"
            path.write_text('{"id": "a"}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "stories.jsonl:1"):
                load_stories(path)

    def test_pick_skips_video_and_used(self):
        items = [
            Story("a", "старая", "2026-10-01"),
            Story("b", "видео", "2026-10-03", media="video"),
            Story("c", "новая", "2026-10-02"),
            Story("d", "уже была", "2026-10-04"),
        ]
        self.assertEqual([s.id for s in pick_stories(items, {"d"}, 5)], ["c", "a"])


class PlannerTest(unittest.TestCase):
    def test_full_day_within_limits(self):
        items = stories(12)
        drafts = {"posts": [{"story_id": s.id, "text": f"Клиент молчал. История {s.id[1:]}."} for s in items]}
        plan, calls = build(items, drafts, per_day=20)
        self.assertEqual(len(plan.posts), MAX_PER_DAY)
        self.assertEqual(plan.warnings, [])
        self.assertEqual(len(calls), 1)
        self.assertIn("Пишу коротко.", calls[0]["body"]["systemInstruction"]["parts"][0]["text"])
        # Берутся самые свежие истории с запасом в две.
        self.assertIn('id="s2"', prompt_of(calls[0]))
        self.assertNotIn('id="s1"', prompt_of(calls[0]))

    def test_failed_draft_is_rewritten_then_rejected(self):
        items = stories(6)
        drafts = {"posts": [{"story_id": s.id, "text": "Клиент молчал."} for s in items]}
        drafts["posts"][0]["text"] = "Давайте разберёмся — клиент молчал."
        drafts["posts"][1]["text"] = "Всем привет, клиент молчал 40 дней."
        plan, calls = build(
            items,
            drafts,
            {"text": "Клиент молчал. Я ждал."},  # исправленный первый
            {"text": "Всем привет, снова."},  # второй остаётся плохим
            per_day=6,
        )
        self.assertEqual(len(plan.posts), 5)
        self.assertEqual([r.story_id for r in plan.rejected], ["s1"])
        self.assertIn("запрещено в профиле голоса", plan.rejected[0].reasons)
        self.assertIn("40", prompt_of(calls[2]))
        self.assertTrue(plan.warnings)

    def test_unknown_story_ids_are_dropped(self):
        plan, _ = build(stories(1), {"posts": [{"story_id": "made-up", "text": "Выдумка."}]})
        self.assertEqual(plan.posts, [])

    def test_no_stories_means_no_calls(self):
        plan, calls = build([])
        self.assertEqual((plan.posts, calls), ([], []))
        self.assertTrue(plan.warnings)

    def test_missing_posts_list_raises(self):
        gemini, _ = fake_gemini({"wrong": []})
        with self.assertRaises(GeminiError):
            FeedWriter(gemini, VOICE).draft(stories(1))

    def test_schedule_is_ordered_and_in_day(self):
        times = schedule(DAY, 8)
        self.assertEqual(times, sorted(times))
        self.assertTrue("08:40" <= times[0] and times[-1] <= "22:20")
        self.assertEqual(times, schedule(DAY, 8))


if __name__ == "__main__":
    unittest.main()
