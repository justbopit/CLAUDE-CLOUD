import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from feed import ai_filter
from feed.generator import Generator, GenerationError
from feed.planner import MAX_PER_DAY, build_day, schedule
from feed.sources import Story, Voice, load_voice, pick_stories

CLEAN = "Клиент три недели молчал. Потом написал в 2 ночи: переделай всё к утру. Половину сделал, вторую нет. Он остался."


class FilterTest(unittest.TestCase):
    def test_clean_post_passes(self):
        self.assertTrue(ai_filter.check(CLEAN).passed, ai_filter.check(CLEAN).feedback())

    def test_hard_markers_reject(self):
        for text in [
            "Давайте разберёмся, почему клиенты молчат.",
            "Это не просто работа, а образ жизни.",
            "Клиент молчал — и это нормально.",
            "Важно отметить: дедлайны врут.",
            "Три правила:\n1. Молчать\n2. Ждать",
            "Пост про работу #работа #фриланс",
            "Ну и ночь 🔥🔥🔥",
            "Сделал половину. А вы как думаете, правильно?",
            "x" * 501,
        ]:
            with self.subTest(text=text[:40]):
                self.assertFalse(ai_filter.check(text).passed)

    def test_soft_markers_need_two(self):
        self.assertTrue(ai_filter.check("Итак, клиент остался.").passed)
        self.assertFalse(ai_filter.check("Итак, ключевой клиент остался.").passed)

    def test_voice_banned_phrase(self):
        verdict = ai_filter.check("Всем привет, клиент остался.", ["всем привет"])
        self.assertFalse(verdict.passed)

    def test_invented_numbers(self):
        story = "Клиент молчал 3 недели и написал в 2 ночи."
        self.assertEqual(ai_filter.invented_numbers("Молчал 3 недели, написал в 2.", story), [])
        self.assertEqual(ai_filter.invented_numbers("Молчал 5 недель.", story), ["5"])


class SourcesTest(unittest.TestCase):
    def test_voice_banned_section(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "voice.md"
            path.write_text("# Голос\n- коротко\n## Никогда не пишу\n- всем привет\n- «мотивация»\n", encoding="utf-8")
            self.assertEqual(load_voice(path).banned, ("всем привет", "мотивация"))

    def test_pick_skips_video_and_used(self):
        stories = [
            Story("a", "старая", "2026-10-01"),
            Story("b", "видео", "2026-10-03", media="video"),
            Story("c", "новая", "2026-10-02"),
            Story("d", "уже была", "2026-10-04"),
        ]
        self.assertEqual([s.id for s in pick_stories(stories, {"d"}, 5)], ["c", "a"])


def fake_client(*payloads):
    """Клиент, который по очереди отдаёт заготовленные JSON-ответы."""
    calls = []
    queue = list(payloads)

    def create(**kwargs):
        calls.append(kwargs)
        payload = queue.pop(0)
        if payload == "refusal":
            return SimpleNamespace(stop_reason="refusal", content=[])
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text=json.dumps(payload, ensure_ascii=False))],
        )

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    return client, calls


VOICE = Voice(text="Пишу коротко.", banned=("всем привет",))


def stories(n):
    return [Story(f"s{i}", f"История номер {i}: клиент молчал.", f"2026-10-{10 + i:02d}") for i in range(n)]


class PlannerTest(unittest.TestCase):
    def test_full_day_within_limits(self):
        items = stories(10)
        drafts = {"posts": [{"story_id": s.id, "text": f"Клиент молчал. История {s.id[1:]}."} for s in items]}
        client, calls = fake_client(drafts)
        plan = build_day(date(2026, 10, 25), VOICE, items, set(), Generator(client, VOICE), per_day=20)
        self.assertEqual(len(plan.posts), MAX_PER_DAY)
        self.assertEqual(plan.warnings, [])
        self.assertEqual(len(calls), 1)
        req = calls[0]
        self.assertEqual(req["model"], "claude-opus-5-5")
        self.assertEqual(req["fallbacks"], "default")
        self.assertEqual(req["output_config"]["format"]["type"], "json_schema")
        self.assertIn("Пишу коротко.", req["system"])

    def test_failed_draft_is_rewritten_then_rejected(self):
        items = stories(6)
        drafts = {"posts": [{"story_id": s.id, "text": "Клиент молчал."} for s in items]}
        drafts["posts"][0]["text"] = "Давайте разберёмся — клиент молчал."
        drafts["posts"][1]["text"] = "Всем привет, клиент молчал 40 дней."
        client, calls = fake_client(
            drafts,
            {"text": "Клиент молчал. Я ждал."},  # исправленный первый
            {"text": "Всем привет, снова."},  # второй остаётся плохим
        )
        plan = build_day(date(2026, 10, 25), VOICE, items, set(), Generator(client, VOICE), per_day=6)
        self.assertEqual(len(plan.posts), 5)
        self.assertEqual([r.story_id for r in plan.rejected], ["s1"])
        self.assertIn("запрещено в профиле голоса", plan.rejected[0].reasons)
        self.assertIn("40", calls[2]["messages"][0]["content"])
        self.assertTrue(plan.warnings)

    def test_unknown_story_ids_are_dropped(self):
        items = stories(1)
        client, _ = fake_client({"posts": [{"story_id": "made-up", "text": "Выдумка."}]})
        plan = build_day(date(2026, 10, 25), VOICE, items, set(), Generator(client, VOICE))
        self.assertEqual(plan.posts, [])

    def test_no_stories_means_no_calls(self):
        client, calls = fake_client()
        plan = build_day(date(2026, 10, 25), VOICE, [], set(), Generator(client, VOICE))
        self.assertEqual((plan.posts, calls), ([], []))
        self.assertTrue(plan.warnings)

    def test_refusal_raises(self):
        client, _ = fake_client("refusal")
        with self.assertRaises(GenerationError):
            Generator(client, VOICE).draft(stories(1))

    def test_schedule_is_ordered_and_in_day(self):
        times = schedule(date(2026, 10, 25), 8)
        self.assertEqual(times, sorted(times))
        self.assertTrue("08:40" <= times[0] and times[-1] <= "22:20")
        self.assertEqual(times, schedule(date(2026, 10, 25), 8))


if __name__ == "__main__":
    unittest.main()
