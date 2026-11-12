"""Integration checks for the JS-free, same-origin Chrome dashboard."""
from __future__ import annotations

import sys
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scanner"))
from dueltrace_cloud_connector import create_server, HOST
from test_dueltrace_cloud_connector import FakeBridge, SHA, TOKEN, ORIGIN


class LocalChromeBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = FakeBridge()
        cls.server = create_server(cls.bridge, allowed_origins=[ORIGIN],
                                   token=TOKEN, port=0)
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.base = f"http://{HOST}:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join(timeout=3)

    def browser_request(self, path, *, origin=None, method="GET", data=None, headers=None):
        h = {}
        if origin is not None:
            h["Origin"] = origin
        if headers:
            h.update(headers)
        body = None if data is None else urllib.parse.urlencode(data).encode("utf-8")
        if body is not None:
            h["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(self.base + path, data=body,
                                     method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status, response.headers, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.headers, exc.read()

    def test_local_html_runs_without_javascript_next_or_pairing_field(self):
        status, headers, body = self.browser_request(
            "/local/", headers={"Sec-Fetch-Site": "none"})
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Content-Type"), "text/html; charset=utf-8")
        self.assertIn(b"frame-ancestors 'none'", headers.get(
            "Content-Security-Policy", "").encode())
        self.assertIn(b"DUELTRACE Cloud", body)
        self.assertIn(b"v0.5.0", body)
        self.assertNotIn(b"<script", body.lower())
        self.assertNotIn(b"__next", body.lower())
        self.assertNotIn(b"Conectar ao computador", body)
        self.assertIn(b"Biblioteca de Mods", body)
        self.assertIn(b"Biblioteca de Cartas", body)
        self.assertIn(b"Fus\xc3\xb5es", body)
        self.assertIn(b"Conex\xc3\xa3o local estabelecida", body)
        self.assertNotIn(b"C:/secret", body)
        self.assertNotIn(b"ram_address", body)

    def test_local_navigation_and_derived_cards_without_js(self):
        status, _, body = self.browser_request("/local/?tab=biblioteca&q=Drag")
        self.assertEqual(status, 200)
        self.assertIn("Dragão".encode(), body)
        self.assertIn(b"ATK", body)
        self.assertNotIn(b"C:/private", body)
        status, _, body = self.browser_request("/local/?tab=fusoes")
        self.assertEqual(status, 200)
        self.assertIn("Fusão".encode(), body)
        status, _, body = self.browser_request("/local/?tab=mods")
        self.assertEqual(status, 200)
        self.assertIn(b'name="csrf"', body)
        self.assertIn(b'name="action"', body)

    def test_clickable_card_details_show_five_hints_total_without_js(self):
        status, _, library = self.browser_request("/local/?tab=biblioteca")
        self.assertEqual(status, 200)
        self.assertIn(b'class="card-link"', library)
        status, _, page = self.browser_request("/local/?tab=carta&id=1")
        self.assertEqual(status, 200)
        self.assertIn(b'class="detail-image"', page)
        self.assertIn(b"5 dicas exibidas", page)
        self.assertIn(b"Fus", page)
        self.assertEqual(page.count(b'class="detail-pair"'), 5)
        self.assertIn(b"Fus\xc3\xb5es provis\xc3\xb3rias", page)
        self.assertNotIn(b"Resultado <teste>", page)
        self.assertIn(b"Resultado &lt;teste&gt;", page)
        self.assertNotIn(b"<script", page.lower())

    def test_invalid_card_id_is_not_read(self):
        status, _, _ = self.browser_request("/local/?tab=carta&id=723")
        self.assertEqual(status, 400)
        status, _, page = self.browser_request("/local/?tab=carta&id=0")
        self.assertEqual(status, 200)
        self.assertIn(b"Carta n\xc3\xa3o encontrada", page)

    def test_html_does_not_reflect_script_in_search_or_query(self):
        payload = "<script>alert(1)</script>"
        status, _, body = self.browser_request(
            "/local/?tab=biblioteca&q=" + urllib.parse.quote(payload))
        self.assertEqual(status, 200)
        self.assertNotIn(payload.encode(), body)
        self.assertIn(b"&lt;script&gt;", body)

    def test_cross_site_frames_and_dns_rebinding_denied(self):
        self.assertEqual(self.browser_request("/local/",
            headers={"Sec-Fetch-Site": "cross-site"})[0], 403)
        self.assertEqual(self.browser_request("/local/",
            headers={"Host": "attacker.example"})[0], 403)
        self.assertEqual(self.browser_request("/local/",
            origin="https://attacker.example")[0], 403)

    def test_form_action_requires_same_origin_and_ephemeral_csrf(self):
        form = {"action": "activate", "sha": SHA, "csrf": TOKEN}
        before = len(self.bridge.activations)
        self.assertEqual(self.browser_request("/local/action",
            method="POST", data=form, origin="https://attacker.example")[0], 403)
        self.assertEqual(self.browser_request("/local/action",
            method="POST", data={**form, "csrf": "invalid"},
            origin=self.base)[0], 403)
        self.assertEqual(self.browser_request("/local/action",
            method="POST", data={"action": "activate", "sha": "../other",
                                  "csrf": TOKEN}, origin=self.base)[0], 400)
        self.assertEqual(len(self.bridge.activations), before)
        status, _, body = self.browser_request("/local/action",
            method="POST", data=form, origin=self.base)
        self.assertEqual(status, 200)  # follows 303 to the local UI
        self.assertEqual(len(self.bridge.activations), before + 1)
        self.assertIn(b"Mod ativado", body)

    def test_original_cross_origin_api_still_requires_secret(self):
        status, _, _ = self.browser_request("/v1/state", origin=ORIGIN)
        self.assertEqual(status, 401)
        status, _, _ = self.browser_request("/v1/state", origin=self.base)
        self.assertEqual(status, 403)
        status, _, _ = self.browser_request("/v1/state")
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()
