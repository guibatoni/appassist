"""Teste offline da consulta de versões; jamais baixa ou executa um binário."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))

from dueltrace_update_checker import (
    CURRENT_VERSION, RELEASE_API, RELEASE_PAGE, check_for_updates,
    fetch_stable_release, open_official_releases, parse_version,
)


def release(tag="v0.6.6", **extra):
    return {
        "tag_name":tag,
        "html_url":"https://github.com/guibatoni/appassist/releases/tag/"+tag,
        "draft":False,
        "prerelease":False,
        **extra,
    }


class UpdateCheckerTests(unittest.TestCase):
    def test_version_numbers_are_compared_numerically(self):
        self.assertEqual(parse_version("v0.7.2"),(0,7,2))
        self.assertEqual(parse_version("0.10.0"),(0,10,0))
        self.assertGreater(parse_version("0.10.0"),parse_version("0.9.9"))
        for invalid in ("",None,"v0.7.2-beta","0.6","0.1.2.3","1.2.3/../",
                        "  v1.2.3foo"):
            self.assertIsNone(parse_version(invalid))

    def test_preview_never_calls_old_stable_an_update(self):
        result=check_for_updates(fetcher=lambda:release("v0.6.6"),
                                 current_version="0.7.2",channel="preview")
        self.assertEqual(result["status"],"preview_ahead")
        self.assertFalse(result["updateAvailable"])
        self.assertEqual(result["latestStable"],"v0.6.6")
        self.assertEqual(result["releasePage"],RELEASE_PAGE)

    def test_new_stable_update_detected_but_no_install_action(self):
        result=check_for_updates(fetcher=lambda:release("v0.8.0"),
                                 current_version="0.7.2",channel="preview")
        self.assertEqual(result["status"],"update_available")
        self.assertTrue(result["updateAvailable"])
        self.assertNotIn("download_url",result)
        self.assertNotIn("executable",result)

    def test_same_version_distinguishes_preview_and_stable(self):
        preview=check_for_updates(fetcher=lambda:release("v0.7.2"),
                                  current_version="0.7.2",channel="preview")
        stable=check_for_updates(fetcher=lambda:release("v0.7.2"),
                                 current_version="0.7.2",channel="stable")
        self.assertEqual(preview["status"],"preview")
        self.assertEqual(stable["status"],"up_to_date")

    def test_malformed_or_foreign_releases_fail_without_url_reflection(self):
        for payload in [
            release("v0.9.0",html_url="https://evil.example/install.exe"),
            release("v0.9.0",draft=True),
            release("v0.9.0",prerelease=True),
            release("not-a-version"),
            {"tag_name":"v0.9.0"},
            [],
        ]:
            with self.subTest(payload=payload):
                status=check_for_updates(fetcher=lambda:payload)
                self.assertEqual(status["status"],"unavailable")
                self.assertFalse(status["updateAvailable"])
                self.assertEqual(status["releasePage"],RELEASE_PAGE)

    def test_offline_network_failure_is_honest(self):
        result=check_for_updates(fetcher=lambda:(_ for _ in ()).throw(OSError("offline")))
        self.assertEqual(result["status"],"unavailable")
        self.assertIn("Não foi possível",result["message"])
        self.assertFalse(result["updateAvailable"])

    def test_open_releases_uses_constant_official_url(self):
        with patch("dueltrace_update_checker.webbrowser.open",return_value=True) as open_browser:
            self.assertTrue(open_official_releases())
            open_browser.assert_called_once_with(RELEASE_PAGE,new=2)

    def test_http_request_has_timeout_and_does_not_follow_redirects(self):
        class DummyHeaders:
            def get(self,key):
                return None
        class DummyResponse:
            status=200
            headers=DummyHeaders()
            def geturl(self):
                return RELEASE_API
            def read(self, max_bytes):
                return b'{"tag_name":"v0.6.6"}'
            def __enter__(self):
                return self
            def __exit__(self,*args):
                pass
        class DummyOpener:
            def open(self, request, timeout):
                self.request=request
                self.timeout=timeout
                return DummyResponse()
        opener=DummyOpener()
        with patch("dueltrace_update_checker.urllib.request.build_opener",return_value=opener):
            data=fetch_stable_release()
        self.assertEqual(data["tag_name"],"v0.6.6")
        self.assertEqual(opener.request.full_url,RELEASE_API)
        self.assertLessEqual(opener.timeout,10)


if __name__=="__main__":
    unittest.main()
