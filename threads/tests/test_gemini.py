import os
import unittest
from unittest import mock

from threadskit import net
from threadskit.gemini import DEFAULT_MODEL, TEXT_SCHEMA, Gemini, GeminiError

from .fakes import fake_gemini


class GeminiTest(unittest.TestCase):
    def test_request_shape(self):
        gemini, calls = fake_gemini({"text": "ok"})
        self.assertEqual(gemini.ask_text("система", "вопрос"), "ok")
        call = calls[0]
        self.assertTrue(call["url"].endswith(f"/models/{DEFAULT_MODEL}:generateContent"))
        self.assertEqual(call["headers"], {"x-goog-api-key": "test-key"})
        self.assertEqual(call["body"]["systemInstruction"], {"parts": [{"text": "система"}]})
        self.assertEqual(call["body"]["contents"][0]["parts"][0]["text"], "вопрос")
        config = call["body"]["generationConfig"]
        self.assertEqual(config["responseMimeType"], "application/json")
        self.assertEqual(config["responseJsonSchema"], TEXT_SCHEMA)

    def test_thought_parts_are_skipped(self):
        raw = {"candidates": [{"finishReason": "STOP", "content": {"parts": [
            {"text": "думаю...", "thought": True},
            {"text": '{"text": "ok"}'},
        ]}}]}
        gemini, _ = fake_gemini(raw)
        self.assertEqual(gemini.ask_text("s", "p"), "ok")

    def test_bad_responses_raise(self):
        for raw in [
            {"promptFeedback": {"blockReason": "SAFETY"}},
            {"candidates": []},
            {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "{"}]}}]},
            {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "не json"}]}}]},
            {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "[1]"}]}}]},
        ]:
            with self.subTest(raw=raw):
                gemini, _ = fake_gemini(raw)
                with self.assertRaises(GeminiError):
                    gemini.ask("s", "p", TEXT_SCHEMA)

    def test_http_error_is_wrapped(self):
        def post(url, body, headers):
            raise net.HTTPError(400, "Invalid JSON payload")

        with self.assertRaisesRegex(GeminiError, "Invalid JSON payload"):
            Gemini("k", post=post).ask("s", "p", TEXT_SCHEMA)

    def test_from_env(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(GeminiError):
                Gemini.from_env()
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "k", "GEMINI_MODEL": "gemini-x"}, clear=True):
            gemini = Gemini.from_env()
            self.assertEqual((gemini.api_key, gemini.model), ("k", "gemini-x"))


if __name__ == "__main__":
    unittest.main()
