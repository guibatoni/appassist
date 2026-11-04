"""Testes offline do verificador de previews futuros (sem rede/instalação)."""
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


def stable(tag="v0.6.6"):
    return {"tag_name":tag,"html_url":
            f"https://github.com/guibatoni/appassist/releases/tag/{tag}",
            "draft":False,"prerelease":False}


def run(run_id,branch=BRANCH,*,conclusion="success",event="push",repo="guibatoni/appassist"):
    return {"id":run_id,"head_branch":branch,"status":"completed",
            "conclusion":conclusion,"event":event,"head_sha":"a"*40,
            "name":previews.WORKFLOW_NAME,
            "head_repository":{"full_name":repo},
            "html_url":f"{previews.REPO_WEB}/actions/runs/{run_id}"}


def preview(run_id=120,branch=BRANCH):
    return {"run_id":run_id,"branch":branch,"head_sha":"a"*40,
            "version":previews.version_for_branch(branch),
            "page":f"{previews.REPO_WEB}/actions/runs/{run_id}",
            "artifact_name":previews.ARTIFACT_NAME}


class PreviewUpdaterTests(unittest.TestCase):
    def test_dynamic_branch_version_supports_future_versions(self):
        self.assertEqual(previews.version_for_branch(BRANCH),"0.7.5")
        self.assertEqual(previews.version_for_branch("feature/dueltrace-v076-new-project"),"0.7.6")
        self.assertEqual(previews.version_for_branch("feature/dueltrace-v100-next"),"1.0.0")
        self.assertIsNone(previews.version_for_branch("main"))
        self.assertIsNone(previews.version_for_branch("feature/evil-v076"))
        self.assertIsNone(previews.version_for_branch("feature/dueltrace-v076-../../bad"))

    def test_newer_preview_build_detected_by_build_id(self):
        x=check_for_updates(fetcher=lambda:stable(),preview_fetcher=lambda:preview(120),
                            current_version="0.7.5",installed_run_id=100)
        self.assertEqual(x["status"],"preview_update_available")
        self.assertTrue(x["updateAvailable"])
        self.assertEqual(x["previewVersion"],"0.7.5")
        self.assertFalse(x["automaticInstallReady"])
        self.assertNotIn("download_url",x)

    def test_future_branch_is_new_version_without_app_code_change(self):
        x=check_for_updates(fetcher=lambda:stable(),
            preview_fetcher=lambda:preview(900,branch="feature/dueltrace-v076-next-version"),
            current_version="0.7.5",installed_run_id=9999)
        self.assertEqual(x["status"],"preview_update_available")
        self.assertTrue(x["updateAvailable"])

    def test_older_branch_with_larger_run_id_never_downgrades(self):
        x=check_for_updates(fetcher=lambda:stable(),
            preview_fetcher=lambda:preview(100000,branch="feature/dueltrace-v074-drops-ranks-frames"),
            current_version="0.7.5",installed_run_id=100)
        self.assertEqual(x["status"],"preview_older")
        self.assertFalse(x["updateAvailable"])

    def test_same_or_newer_installed_build_is_current(self):
        for installed in (120,130):
            x=check_for_updates(fetcher=lambda:stable(),preview_fetcher=lambda:preview(120),
                                installed_run_id=installed,current_version="0.7.5")
            self.assertEqual(x["status"],"preview_current")
            self.assertFalse(x["updateAvailable"])

    def test_old_preview_without_build_id_does_not_guess(self):
        with patch("dueltrace_update_checker.installed_preview_build_id",return_value=None):
            x=check_for_updates(fetcher=lambda:stable(),preview_fetcher=lambda:preview(120),
                                current_version="0.7.5")
        self.assertEqual(x["status"],"preview_build_unknown")
        self.assertFalse(x["updateAvailable"])

    def test_stable_newer_remains_priority(self):
        x=check_for_updates(fetcher=lambda:stable("v0.9.6"),
            preview_fetcher=lambda:preview(120),installed_run_id=100)
        self.assertEqual(x["status"],"update_available")
        self.assertTrue(x["updateAvailable"])

    def test_foreign_or_mismatched_preview_rejected(self):
        for bad in (
            {**preview(),"page":"https://evil.example"},
            {**preview(),"version":"9.9.9"},
            {**preview(),"branch":"feature/evil-v075"},
        ):
            with self.subTest(payload=bad):
                x=check_for_updates(fetcher=lambda:stable(),preview_fetcher=lambda:bad)
                self.assertEqual(x.get("previewStatus"),"unavailable")
                self.assertIsNone(x["previewRunId"])

    def test_only_official_successful_push_workflow_accepted(self):
        self.assertTrue(previews._accepted_run(run(202)))
        for tampered in (
            run(202,event="pull_request"),
            run(202,repo="other/fork"),
            {**run(202),"name":"Outro workflow"},
            {**run(202),"html_url":"https://evil.example"},
            run(202,conclusion="failure"),
        ):
            self.assertFalse(previews._accepted_run(tampered))

    def test_selects_highest_version_not_highest_run_id(self):
        future=run(100,"feature/dueltrace-v076-future")
        older=run(200,"feature/dueltrace-v075-rank-forensics-safe-updater")
        calls=[]
        def fake_json(url):
            calls.append(url)
            if url==previews.RUNS_API:
                return {"workflow_runs":[older,future]}
            if "/100/artifacts?" in url:
                return {"artifacts":[{"name":previews.ARTIFACT_NAME,"expired":False}]}
            raise AssertionError(url)
        with patch.object(previews,"_get_json",side_effect=fake_json):
            picked=previews.fetch_latest_preview()
        self.assertEqual(picked["run_id"],100)
        self.assertEqual(picked["version"],"0.7.6")
        self.assertEqual(len(calls),2)

    def test_expired_or_failed_runs_are_not_available(self):
        def fake_json(url):
            if url==previews.RUNS_API:
                return {"workflow_runs":[run(300,event="pull_request"),run(201)]}
            if "/201/artifacts?" in url:
                return {"artifacts":[{"name":previews.ARTIFACT_NAME,"expired":True}]}
            raise AssertionError(url)
        with patch.object(previews,"_get_json",side_effect=fake_json):
            self.assertIsNone(previews.fetch_latest_preview())

    def test_build_identity_read_from_embedded_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/previews.BUILD_INFO_FILE
            p.write_text(json.dumps({"schema":1,"run_id":100,
                                     "head_sha":"a"*40,"version":"0.7.5"}))
            with patch.object(previews.sys,"_MEIPASS",folder,create=True):
                self.assertEqual(previews.installed_preview_build_id(),100)
                p.write_text('{"schema":1,"run_id":"100"}')
                self.assertIsNone(previews.installed_preview_build_id())

    def test_only_official_urls_may_open(self):
        with patch("dueltrace_update_checker.webbrowser.open",return_value=True) as op:
            self.assertTrue(open_official_releases(120))
            op.assert_called_with(
                "https://github.com/guibatoni/appassist/actions/runs/120",new=2)
            self.assertTrue(open_official_releases(0))
        for bad in ("120",-1,10**15,True):
            with self.assertRaises(ValueError):
                open_official_releases(bad)


if __name__=="__main__":
    unittest.main()
