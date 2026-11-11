"""Offline regressions for public ZIP Preview discovery without GitHub Actions."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
import dueltrace_preview_updates as previews
from dueltrace_update_checker import check_for_updates, open_official_releases

BRANCH="feature/dueltrace-v075-rank-forensics-safe-updater"
PUBLIC="https://github.com/guibatoni/dueltrace-releases"


def stable(tag="v0.6.6"):
    return {"tag_name":tag,
            "html_url":f"{PUBLIC}/releases/tag/{tag}",
            "draft":False,"prerelease":False}


def preview(run_id=120,version="0.7.5"):
    return {"run_id":run_id,"version":version,"sha":"a"*40,
            "page":f"{PUBLIC}/releases/tag/preview-v{version}-r{run_id}"}


class PreviewUpdaterTests(unittest.TestCase):
    def test_branch_versions_still_supported_offline_for_legacy_profiles(self):
        self.assertEqual(previews.version_for_branch(BRANCH),"0.7.5")
        self.assertEqual(previews.version_for_branch("feature/dueltrace-v076-next"),"0.7.6")
        self.assertEqual(previews.version_for_branch("feature/dueltrace-v100-next"),"1.0.0")
        self.assertEqual(previews.version_for_branch(
            "feature/dueltrace-v0.10.0-next"),"0.10.0")
        self.assertIsNone(previews.version_for_branch("main"))
        self.assertIsNone(previews.version_for_branch("feature/evil-v076"))

    def test_semver_branches_and_injection_are_validated(self):
        for branch,version in (
            ("feature/dueltrace-v096-legacy","0.9.6"),
            ("feature/dueltrace-v0.10.0-layout","0.10.0"),
            ("fix/dueltrace-v0.10.12-cards","0.10.12"),
            ("security/dueltrace-v12.34.56-updater","12.34.56"),
            ("feature/dueltrace-v9999.9999.9999-next","9999.9999.9999"),
        ):
            with self.subTest(branch=branch):
                self.assertEqual(previews.version_for_branch(branch),version)
        for branch in (
            None,100,"feature/dueltrace-v0100-no",
            "feature/dueltrace-v00.10.0-leading-zeros",
            "feature/dueltrace-v0.010.0-leading-zeros",
            "feature/dueltrace-v0.10.00-leading-zeros",
            "feature/dueltrace-v0.10.0.1-too-many",
            "feature/dueltrace-v10000.0.0-too-big",
            "feature/dueltrace-v0.10.0+build-next",
            "feature/dueltrace-v０.10.0-unicode",
            "feature/dueltrace-v0.10.0-../../escape",
            "feature/dueltrace-v0.10.0-$(command)",
            "feature/dueltrace-v0.10.0-safe;command",
            "feature/dueltrace-v0.10.0-safe%2fescape",
            "feature/dueltrace-v0.10.0-safe\\n",
        ):
            with self.subTest(branch=branch):
                self.assertIsNone(previews.version_for_branch(branch))

    def test_preview_compared_by_version_and_build_from_public_release(self):
        for old_version,old_build,latest,expected,available in (
            ("0.9.9",100,preview(200,"0.10.0"),"preview_update_available",True),
            ("0.10.0",100,preview(200,"0.9.9"),"preview_older",False),
            ("0.7.5",100,preview(120),"preview_update_available",True),
            ("0.7.5",120,preview(120),"preview_current",False),
            ("0.7.5",130,preview(120),"preview_current",False),
            ("0.7.5",None,preview(120),"preview_build_unknown",False),
        ):
            with self.subTest(case=(old_version,old_build,latest["version"])):
                patched=(patch("dueltrace_update_checker.installed_preview_build_id",
                               return_value=None) if old_build is None else
                         patch("dueltrace_update_checker.installed_preview_build_id",
                               return_value=old_build))
                with patched:
                    result=check_for_updates(
                        fetcher=lambda:stable(),
                        preview_fetcher=lambda:latest,
                        current_version=old_version,
                        installed_run_id=old_build)
                self.assertEqual(result["status"],expected)
                self.assertEqual(result["updateAvailable"],available)
                self.assertFalse(result["automaticInstallReady"])
                self.assertNotIn("download_url",result)

    def test_stable_newer_still_has_priority(self):
        result=check_for_updates(
            fetcher=lambda:stable("v0.9.8"),
            preview_fetcher=lambda:preview(300,"0.10.0"),
            current_version="0.9.7",installed_run_id=100)
        self.assertEqual(result["status"],"update_available")
        self.assertTrue(result["updateAvailable"])

    def test_foreign_or_incomplete_public_previews_fail_closed(self):
        p=preview(120)
        for bad in (
            {**p,"page":"https://evil.example/release"},
            {**p,"page":"https://github.com/guibatoni/appassist/actions/runs/120"},
            {**p,"version":"9.9.9"},
            {**p,"sha":"invalid"},
            {**p,"run_id":True},
        ):
            with self.subTest(bad=bad):
                status=check_for_updates(
                    fetcher=lambda:stable(),
                    preview_fetcher=lambda:bad,
                    current_version="0.7.5",installed_run_id=100)
                self.assertEqual(status.get("previewStatus"),"unavailable")
                self.assertIsNone(status["previewRunId"])
                self.assertFalse(status["updateAvailable"])

    def test_legacy_fetch_latest_preview_is_public_package_wrapper(self):
        package={"run_id":120,"sha":"a"*40,"version":"0.7.5",
                 "page":f"{PUBLIC}/releases/tag/preview-v0.7.5-r120"}
        with patch("dueltrace_preview_installer.fetch_latest_preview_package",
                   return_value=package) as selector:
            found=previews.fetch_latest_preview()
        selector.assert_called_once_with(
            current_version="0.0.0",installed_run_id=0)
        self.assertEqual(found["head_sha"],"a"*40)
        self.assertEqual(found["page"],package["page"])
        self.assertEqual(found["run_id"],120)
        self.assertNotIn("artifact_name",found)
        with patch("dueltrace_preview_installer.fetch_latest_preview_package",
                   return_value=None):
            self.assertIsNone(previews.fetch_latest_preview())

    def test_private_actions_endpoints_are_not_present_in_client_module(self):
        source=(Path(__file__).resolve().parents[1]/
                "scanner/dueltrace_preview_updates.py").read_text(
                    encoding="utf-8")
        self.assertEqual(previews.REPO_WEB,PUBLIC)
        self.assertIn('/releases?per_page=30',previews.RELEASES_API)
        self.assertNotIn('/actions/',source)
        self.assertNotIn('guibatoni/appassist',source)
        self.assertNotIn('WORKFLOW_NAME',source)
        self.assertNotIn('ARTIFACT_NAME',source)
        self.assertNotIn('GH_TOKEN',source)

    def test_only_public_url_is_accepted_by_json_helper(self):
        for hostile in (
            "https://api.github.com/repos/guibatoni/appassist/releases",
            "https://evil.example/releases",
            "https://api.github.com/repos/guibatoni/dueltrace-releases.evil/releases",
        ):
            with self.subTest(url=hostile),self.assertRaises(ValueError):
                previews._get_json(hostile)

    def test_build_identity_read_from_embedded_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/previews.BUILD_INFO_FILE
            p.write_text(json.dumps({"schema":1,"run_id":20261111164500,
                                     "head_sha":"a"*40,"version":"0.9.7"}))
            with patch.object(previews.sys,"_MEIPASS",folder,create=True):
                self.assertEqual(previews.installed_preview_build_id(),20261111164500)
                p.write_text('{"schema":1,"run_id":"20261111164500"}')
                self.assertIsNone(previews.installed_preview_build_id())

    def test_official_browser_links_never_use_private_source(self):
        with patch("dueltrace_update_checker.webbrowser.open",return_value=True) as op:
            self.assertTrue(open_official_releases(120))
            op.assert_called_with(f"{PUBLIC}/releases",new=2)
            self.assertTrue(open_official_releases(0))
        for bad in ("120",-1,10**15,True):
            with self.assertRaises(ValueError):
                open_official_releases(bad)


if __name__=="__main__":
    unittest.main()
