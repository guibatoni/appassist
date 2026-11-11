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

    def test_explicit_semver_branches_and_legacy_versions_are_canonical(self):
        for branch, expected in (
            ("feature/dueltrace-v096-legacy", "0.9.6"),
            ("feature/dueltrace-v0.10.0-universal-layout", "0.10.0"),
            ("fix/dueltrace-v0.10.12-cards", "0.10.12"),
            ("security/dueltrace-v12.34.56-updater", "12.34.56"),
            ("feature/dueltrace-v9999.9999.9999-boundary", "9999.9999.9999"),
        ):
            with self.subTest(branch=branch):
                self.assertEqual(previews.version_for_branch(branch), expected)

    def test_ambiguous_or_injected_semver_branches_are_rejected(self):
        for branch in (
            None, 100, "feature/dueltrace-v0100-ambiguous",
            "feature/dueltrace-v00.10.0-leading-zero",
            "feature/dueltrace-v0.010.0-leading-zero",
            "feature/dueltrace-v0.10.00-leading-zero",
            "feature/dueltrace-v0.10-incomplete",
            "feature/dueltrace-v0.10.0.1-extra-component",
            "feature/dueltrace-v10000.0.0-too-large",
            "feature/dueltrace-v0.10.0-", "feature/dueltrace-v0.10.0",
            "feature/dueltrace-v0.10.0+build-next",
            "feature/dueltrace-v０.10.0-unicode",
            "other/dueltrace-v0.10.0-untrusted",
            "feature/dueltrace-v0.10.0-../../escape",
            "feature/dueltrace-v0.10.0-$(command)",
            "feature/dueltrace-v0.10.0-safe;command",
            "feature/dueltrace-v0.10.0-safe%2fescape",
            "feature/dueltrace-v0.10.0-safe\n",
            " feature/dueltrace-v0.10.0-safe",
        ):
            with self.subTest(branch=branch):
                self.assertIsNone(previews.version_for_branch(branch))

    def test_double_digit_minor_is_an_update_and_never_a_downgrade(self):
        for local, branch, status, available in (
            ("0.9.9", "feature/dueltrace-v0.10.0-universal-layout",
             "preview_update_available", True),
            ("0.10.0", "feature/dueltrace-v099-legacy",
             "preview_older", False),
        ):
            with self.subTest(local=local, branch=branch):
                result=check_for_updates(fetcher=lambda:stable(),
                    preview_fetcher=lambda:preview(900, branch=branch),
                    current_version=local, installed_run_id=9999)
                self.assertEqual(result["status"], status)
                self.assertEqual(result["updateAvailable"], available)
                self.assertFalse(result["automaticInstallReady"])

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
        x=check_for_updates(fetcher=lambda:stable("v0.9.8"),
            preview_fetcher=lambda:preview(120,
                branch="feature/dueltrace-v0.10.0-universal-layout"),
            current_version="0.9.7",installed_run_id=100)
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

    def test_semver_ordering_crosses_minor_boundary_and_ties_by_build(self):
        for candidates, expected_id, expected_version in (
            ([run(900, "feature/dueltrace-v099-legacy"),
              run(100, "feature/dueltrace-v0.10.0-universal-layout")], 100, "0.10.0"),
            ([run(900, "feature/dueltrace-v0.10.0-universal-layout"),
              run(100, "feature/dueltrace-v100-next")], 100, "1.0.0"),
            ([run(100, "feature/dueltrace-v096-legacy"),
              run(200, "fix/dueltrace-v0.9.6-rebuilt")], 200, "0.9.6"),
        ):
            with self.subTest(expected_version=expected_version):
                def fake_json(url):
                    if url == previews.RUNS_API:
                        return {"workflow_runs": candidates}
                    self.assertEqual(url,
                        f"{previews.REPO_API}/actions/runs/{expected_id}/artifacts?per_page=100")
                    return {"artifacts":[{"name":previews.ARTIFACT_NAME,"expired":False}]}
                with patch.object(previews,"_get_json",side_effect=fake_json):
                    picked=previews.fetch_latest_preview()
                self.assertEqual(picked["run_id"], expected_id)
                self.assertEqual(picked["version"], expected_version)

    def test_semver_does_not_relax_official_workflow_checks(self):
        branch="feature/dueltrace-v0.10.0-universal-layout"
        self.assertTrue(previews._accepted_run(run(202, branch)))
        for tampered in (
            run(202, branch, event="pull_request"),
            run(202, branch, repo="other/fork"),
            {**run(202, branch), "name":"Untrusted workflow"},
            {**run(202, branch), "head_sha":"not-a-commit"},
            {**run(202, branch), "html_url":"https://evil.example/run/202"},
        ):
            with self.subTest(run=tampered):
                self.assertFalse(previews._accepted_run(tampered))

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
                "https://github.com/guibatoni/dueltrace-releases/releases",new=2)
            self.assertTrue(open_official_releases(0))
        for bad in ("120",-1,10**15,True):
            with self.assertRaises(ValueError):
                open_official_releases(bad)


if __name__=="__main__":
    unittest.main()
