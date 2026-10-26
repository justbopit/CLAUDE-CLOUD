import unittest

from threadskit import ai_filter

CLEAN = "Клиент три недели молчал. Потом написал в 2 ночи: переделай всё к утру. Половину сделал, вторую нет. Он остался."


class FilterTest(unittest.TestCase):
    def test_clean_post_passes(self):
        self.assertTrue(ai_filter.check(CLEAN).passed, ai_filter.check(CLEAN).feedback())

    def test_hard_markers_reject(self):
        for text in [
            "Давайте разберёмся, почему клиенты молчат.",
            "Это не просто работа, а образ жизни.",
            "Клиент молчал — и всё.",
            "Важно отметить: дедлайны врут.",
            "В мире, где все спешат, клиент молчал.",
            "Три правила:\n1. Молчать\n2. Ждать",
            "Пост про работу #работа #фриланс",
            "Ну и ночь 🔥🔥🔥",
            "Сделал половину. А вы как думаете, правильно?",
            "**Клиент** молчал.",
            "x" * 501,
        ]:
            with self.subTest(text=text[:40]):
                self.assertFalse(ai_filter.check(text).passed)

    def test_soft_markers_need_two(self):
        self.assertTrue(ai_filter.check("Итак, клиент остался.").passed)
        self.assertFalse(ai_filter.check("Итак, ключевой клиент остался.").passed)
        self.assertFalse(ai_filter.check("Клиент молчал. И знаете что? И это нормально.").passed)

    def test_voice_banned_phrase(self):
        self.assertFalse(ai_filter.check("Всем привет, клиент остался.", ["всем привет"]).passed)

    def test_invented_numbers(self):
        story = "Клиент молчал 3 недели и написал в 2 ночи."
        self.assertEqual(ai_filter.invented_numbers("Молчал 3 недели, написал в 2.", story), [])
        self.assertEqual(ai_filter.invented_numbers("Молчал 5 недель.", story), ["5"])

    def test_invented_links(self):
        source = "Портфолио: https://example.com/work."
        self.assertEqual(ai_filter.invented_links("Смотрите https://example.com/work", source), [])
        self.assertEqual(ai_filter.invented_links("Пишите в t.me/scam", source), ["t.me/scam"])
        self.assertIn("ссылки", ai_filter.problems("Жми www.scam.ru", source))

    def test_polish_rewrites_once(self):
        calls = []

        def rewrite(text, issues):
            calls.append(issues)
            return "Клиент молчал."

        text, issues = ai_filter.polish("Давайте разберёмся — клиент молчал 40 дней.", "Клиент молчал.", (), rewrite)
        self.assertEqual((text, issues), ("Клиент молчал.", ""))
        self.assertEqual(len(calls), 1)
        self.assertIn("длинное тире", calls[0])
        self.assertIn("40", calls[0])

    def test_polish_gives_up_after_attempts(self):
        text, issues = ai_filter.polish("Всем привет.", "", ("всем привет",), lambda t, i: "Всем привет!")
        self.assertEqual(text, "Всем привет!")
        self.assertIn("запрещено в профиле голоса", issues)

    def test_polish_skips_rewrite_for_clean_text(self):
        def rewrite(text, issues):
            raise AssertionError("чистый текст не переписываем")

        self.assertEqual(ai_filter.polish(CLEAN, CLEAN, (), rewrite), (CLEAN, ""))


if __name__ == "__main__":
    unittest.main()
