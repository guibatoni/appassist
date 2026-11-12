"""Online DUELTRACE portal: exact-origin isolation and static build contract."""
from __future__ import annotations
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scanner"))
from dueltrace_cloud_connector import create_server, DEFAULT_ALLOWED_ORIGINS, HOST
from test_dueltrace_cloud_connector import FakeBridge, TOKEN

ONLINE = "https://dueltrace-cloud.vercel.app"


class OnlineCloudTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = create_server(FakeBridge(),
                                 allowed_origins=DEFAULT_ALLOWED_ORIGINS,
                                 token=TOKEN, port=0)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://{HOST}:{cls.http.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join(timeout=5)

    def request(self, *, origin=ONLINE, token=TOKEN,
                method="GET", path="/v1/state", headers=None):
        h = {"Origin": origin}
        if token is not None:
            h["Authorization"] = "Bearer " + token
        if headers:
            h.update(headers)
        req = urllib.request.Request(self.url + path, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=5) as res:
                return res.status, res.headers, res.read()
        except urllib.error.HTTPError as err:
            return err.code, err.headers, err.read()

    def test_exact_published_cloud_origin_gets_local_derived_data(self):
        code, headers, body = self.request()
        self.assertEqual(code, 200)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), ONLINE)
        self.assertIn(b'"storage":"local-only"', body)
        self.assertIn(b'"cloudUpload":false', body)
        self.assertNotIn(b"C:/secret", body)
        self.assertNotIn(b"ram_address", body)

    def test_private_network_preflight_exact_origin_only(self):
        headers = {"Access-Control-Request-Method": "GET",
                   "Access-Control-Request-Headers": "authorization",
                   "Access-Control-Request-Private-Network": "true"}
        code, response, _ = self.request(token=None, method="OPTIONS",
                                         headers=headers)
        self.assertEqual(code, 204)
        self.assertEqual(response.get("Access-Control-Allow-Private-Network"), "true")
        self.assertEqual(response.get("Access-Control-Allow-Origin"), ONLINE)
        for evil in ("https://evil.vercel.app", "https://dueltrace-cloud.vercel.app.evil.test",
                     "http://dueltrace-cloud.vercel.app", "null", ""):
            with self.subTest(origin=evil):
                code, response, _ = self.request(
                    origin=evil, token=None, method="OPTIONS", headers=headers)
                self.assertEqual(code, 403)
                self.assertIsNone(response.get("Access-Control-Allow-Private-Network"))
                self.assertIsNone(response.get("Access-Control-Allow-Origin"))

    def test_remote_origin_alone_never_authenticates(self):
        self.assertEqual(self.request(token=None)[0], 401)
        self.assertEqual(self.request(token="bad")[0], 401)
        self.assertEqual(self.request(origin="https://unknown.vercel.app")[0], 403)

    def test_independent_web_portal_contains_no_persistent_credentials(self):
        base = ROOT / "web" / "public" / "cloud-online"
        html = (base / "index.html").read_text(encoding="utf-8")
        js = (base / "app.js").read_text(encoding="utf-8")
        css = (base / "app.css").read_text(encoding="utf-8")
        self.assertIn("DUELTRACE Cloud", html)
        self.assertIn('script defer src="./app.js"', html)
        self.assertIn("DUELTRACE", css)
        self.assertIn('const BASE = "http://127.0.0.1:8765"', js)
        self.assertIn("response.json()", js)
        self.assertIn("credentials: \"omit\"", js)
        self.assertIn("Authorization: \"Bearer \" + token", js)
        self.assertNotIn("localStorage", js)
        self.assertNotIn("sessionStorage", js)
        self.assertNotIn("innerHTML", js.replace("Never use innerHTML", ""))
        self.assertNotIn("navigator.sendBeacon", js)
        self.assertNotIn("FormData(", js)
        self.assertNotIn("new FileReader(", js)
        self.assertNotIn("https://api.", js)
        self.assertIn("Conectar ao PC", html)

    def test_windows_launcher_has_explicit_key_copy_not_log(self):
        gui = (ROOT / "scanner" / "dueltrace_cloud_windows.py").read_text(
            encoding="utf-8")
        self.assertIn("session_token = secrets.token_urlsafe(32)", gui)
        self.assertIn("root.clipboard_append(session_token)", gui)
        self.assertIn("command=copy_key", gui)
        self.assertIn("DEFAULT_ALLOWED_ORIGINS", gui)
        self.assertNotIn("print(session_token)", gui)
        self.assertNotIn("session_token + ONLINE_URL", gui)


if __name__ == "__main__":
    unittest.main()
