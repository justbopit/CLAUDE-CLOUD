import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from threadskit import net


class Handler(BaseHTTPRequestHandler):
    # Очередь ответов сервера: (статус, тело).
    replies: list = []
    seen: list = []

    def _reply(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode() if length else ""
        Handler.seen.append((self.command, self.path, body, self.headers.get("x-goog-api-key")))
        status, payload = Handler.replies.pop(0)
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = _reply

    def log_message(self, *args):
        pass


class NetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/v1/x"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        Handler.replies, Handler.seen = [], []

    def test_post_json_with_params_and_headers(self):
        Handler.replies = [(200, {"ok": "да"})]
        result = net.request_json("POST", self.url, params={"q": "ищу дизайнера"},
                                  body={"текст": "привет"}, headers={"x-goog-api-key": "k"})
        self.assertEqual(result, {"ok": "да"})
        method, path, body, key = Handler.seen[0]
        self.assertEqual((method, key), ("POST", "k"))
        self.assertIn("q=%D0%B8%D1%89%D1%83", path)
        self.assertEqual(json.loads(body), {"текст": "привет"})

    def test_retries_rate_limit(self):
        pauses = []
        Handler.replies = [(429, {"error": {"message": "slow down"}}), (200, {"ok": 1})]
        self.assertEqual(net.request_json("GET", self.url, sleep=pauses.append), {"ok": 1})
        self.assertEqual(pauses, [2])

    def test_no_retry_when_disabled(self):
        Handler.replies = [(503, {"error": {"message": "busy"}})]
        with self.assertRaises(net.HTTPError) as ctx:
            net.request_json("POST", self.url, params={"access_token": "secret"}, retries=0)
        self.assertEqual(ctx.exception.status, 503)
        self.assertEqual(str(ctx.exception), "HTTP 503: busy")
        self.assertEqual(len(Handler.seen), 1)

    def test_client_error_is_not_retried(self):
        Handler.replies = [(400, {"error": {"message": "Invalid JSON payload"}})]
        with self.assertRaisesRegex(net.HTTPError, "Invalid JSON payload"):
            net.request_json("POST", self.url, body={}, sleep=lambda _: None)
        self.assertEqual(len(Handler.seen), 1)


if __name__ == "__main__":
    unittest.main()
