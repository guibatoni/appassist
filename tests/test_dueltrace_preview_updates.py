"""Testes offline: canais Preview do GitHub Actions, sem downloads."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scanner"))
import dueltrace_preview_updates as previews
from dueltrace_update_checker import check_for_updates, open_official_releases


def stable(tag="v0.6.6"):
    return {"tag_name": tag, "html_url":
            f"https://github.com/guibatoni/appassist/releases/tag/{tag}",
            "draft": False, "prerelease": False}


def run(run_id, branch=None, *, conclusion="success", page=None):
    branch = branch or previews.PREVIEW_BRANCHES[0]
    return {"id": run_id, "head_branch": branch, "status": "completed",
            "conclusion": conclusion, "event": "push", "head_sha": "a"*40,
            "html_url": page or f"{previews.REPO_WEB}/actions/runs/{run_id}"}


def preview(run_id=120):
    return {"run_id": run_id, "branch": previews.PREVIEW_BRANCHES[0],
            "head_sha": "a"*40,
            "page": f"{previews.REPO_WEB}/actions/runs/{run_id}",
            "artifact_name": previews.ARTIFACT_NAME}


class PreviewUpdaterTests(unittest.TestCase):
    def test_newer_preview_build_is_reported(self):
        data=check_for_updates(
            fetcher=lambda: stable(),preview_fetcher=lambda:preview(120),
            current_version="0.7.3",installed_run_id=100)
        self.assertEqual(data["status"], "preview_update_available")
        self.assertTrue(data["updateAvailable"])
        self.assertEqual(data["previewRunId"],120)
        self.assertEqual(data["previewBuildSha"],"a"*10)
        self.assertNotIn("download_url",data)

    def test_same_or_newer_installed_build_is_current(self):
        for installed in (120,130):
            with self.subTest(installed=installed):
                data=check_for_updates(
                    fetcher=lambda:stable(),preview_fetcher=lambda:preview(120),
                    installed_run_id=installed)
                self.assertEqual(data["status"],"preview_current")
                self.assertFalse(data["updateAvailable"])

    def test_legacy_preview_without_build_id_does_not_claim_newer(self):
        with patch("dueltrace_update_checker.installed_preview_build_id",
                   return_value=None):
            data=check_for_updates(
                fetcher=lambda:stable(),preview_fetcher=lambda:preview(120),
                current_version="0.7.4")
        self.assertEqual(data["status"],"preview_build_unknown")
        self.assertFalse(data["updateAvailable"])
        self.assertEqual(data["previewRunId"],120)

    def test_old_minor_preview_offers_newer_package(self):
        data=check_for_updates(
            fetcher=lambda:stable(),preview_fetcher=lambda:preview(120),
            current_version="0.7.2",installed_run_id=0)
        self.assertEqual(data["status"],"preview_update_available")
        self.assertTrue(data["updateAvailable"])

    def test_stable_release_newer_takes_priority(self):
        data=check_for_updates(
            fetcher=lambda:stable("v0.9.0"),
            preview_fetcher=lambda:preview(120),installed_run_id=100)
        self.assertEqual(data["status"],"update_available")
        self.assertTrue(data["updateAvailable"])
        self.assertEqual(data["previewRunId"],120)

    def test_forged_actions_url_is_rejected(self):
        data=check_for_updates(fetcher=lambda:stable(),
              preview_fetcher=lambda:{**preview(120),"page":"https://evil.example/"})
        self.assertIsNone(data["previewPage"])
        self.assertEqual(data["previewStatus"],"unavailable")

    def test_selects_recent_success_with_artifact(self):
        newest=run(202)
        older=run(201, previews.PREVIEW_BRANCHES[1])
        calls=[]
        def get_json(url):
            calls.append(url)
            if "/actions/runs?" in url:
                return {"workflow_runs": [newest] if
                        "preview-update-button" in url else [older]}
            if "/202/artifacts?" in url:
                return {"artifacts":[{"name":previews.ARTIFACT_NAME,"expired":False}]}
            raise AssertionError(url)
        with patch.object(previews,"_get_json",side_effect=get_json):
            found=previews.fetch_latest_preview()
        self.assertEqual(found["run_id"],202)
        self.assertEqual(found["page"],newest["html_url"])
        self.assertEqual(len(calls),len(previews.PREVIEW_BRANCHES)+1)

    def test_ignores_expired_or_failed_builds(self):
        def get_json(url):
            if "/actions/runs?" in url:
                return {"workflow_runs":[run(202,conclusion="failure"),
                                         run(201)] if
                        "preview-update-button" in url else []}
            if "/201/artifacts?" in url:
                return {"artifacts":[{"name":previews.ARTIFACT_NAME,"expired":True}]}
            raise AssertionError(url)
        with patch.object(previews,"_get_json",side_effect=get_json):
            self.assertIsNone(previews.fetch_latest_preview())

    def test_build_identity_read_from_embedded_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/previews.BUILD_INFO_FILE
            p.write_text(json.dumps({"schema":1,"run_id":100,
                                     "head_sha":"a"*40,"version":"0.7.3"}))
            with patch.object(previews.sys,"_MEIPASS",folder,create=True):
                self.assertEqual(previews.installed_preview_build_id(),100)
                p.write_text('{"schema":1,"run_id":"100"}')
                self.assertIsNone(previews.installed_preview_build_id())

    def test_only_official_action_urls_may_open(self):
        with patch("dueltrace_update_checker.webbrowser.open",return_value=True) as op:
            self.assertTrue(open_official_releases(120))
            op.assert_called_with(
                "https://github.com/guibatoni/appassist/actions/runs/120",new=2)
            self.assertTrue(open_official_releases(0))
            op.assert_called_with(
                "https://github.com/guibatoni/appassist/actions/workflows/validar-webui-desktop.yml",new=2)
        for bad in ("120",-1,10**15,True):
            with self.assertRaises(ValueError):
                open_official_releases(bad)


if __name__=="__main__":
    unittest.main()
