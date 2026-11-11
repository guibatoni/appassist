"""Public-only customer update channel: metadata and integrity regression tests."""
from __future__ import annotations

import hashlib
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))

import dueltrace_public_distribution as public
import dueltrace_preview_installer as installer
import dueltrace_update_checker as checker
from dueltrace_signed_install import UnsafeUpdate


SHA="1"*40
RUN=42967559607
ZIP=b"checked-test-archive"
DIGEST=hashlib.sha256(ZIP).hexdigest()
TAG=f"preview-v0.9.7-r{RUN}"


def release(*,tag=TAG,sha=SHA,digest=DIGEST,body=None):
    return {
        "draft":False, "prerelease":True,"tag_name":tag,
        "target_commitish":"main",  # public repo does not have private commit
        "body":(body if body is not None else
                f"Update notes\nBuild {RUN} | Commit {sha} | SHA-256 ZIP: {digest}"),
        "html_url":public.PUBLIC_UPDATES_WEB+"/releases/tag/"+tag,
        "assets":[{"name":installer.ASSET_NAME,
                   "size":len(ZIP),"digest":"sha256:"+digest,
                   "browser_download_url":public.PUBLIC_UPDATES_WEB
                     +"/releases/download/"+tag+"/"+installer.ASSET_NAME}],
    }


class PublicCustomerUpdatesTests(unittest.TestCase):
    def test_uses_distinct_public_repo_without_embedded_credentials(self):
        self.assertEqual(public.PUBLIC_UPDATES_REPO,"guibatoni/dueltrace-releases")
        self.assertEqual(checker.RELEASE_API,public.PUBLIC_UPDATES_API+"/releases/latest")
        self.assertEqual(installer.PREVIEW_LIST,public.PUBLIC_UPDATES_API+"/releases?per_page=30")
        self.assertEqual(checker.RELEASE_PAGE,public.PUBLIC_UPDATES_WEB+"/releases")
        ui=(ROOT/"web/components/shell/update-checker.tsx").read_text(encoding="utf-8")
        self.assertNotIn("gh auth login",ui)
        self.assertNotIn("authentication_required",ui)
        self.assertIn("sem",ui.lower())

    def test_uses_private_source_commit_embedded_in_public_release_notes(self):
        metadata=release()
        result=installer.select_preview_release(metadata,"0.9.7",RUN-1)
        self.assertEqual(result["sha"],SHA)
        self.assertEqual(result["run_id"],RUN)
        self.assertEqual(result["sha256"],DIGEST)
        self.assertEqual(result["url"],public.PUBLIC_UPDATES_WEB
                         +"/releases/download/"+TAG+"/"+installer.ASSET_NAME)
        self.assertNotIn("transport",result)

    def test_fail_closed_on_forged_source_identity(self):
        original=release()
        for tampered in (
            {"body":"missing footer"},
            {"body":original["body"]+"\n"+original["body"]},
            {"body":original["body"].replace(str(RUN),"333333333")},
            {"body":original["body"].replace(DIGEST,"0"*64)},
            {"html_url":"https://bad.example/releases/tag/"+TAG},
            {"assets":[{**original["assets"][0],
                       "browser_download_url":"https://other.example/zip"}]},
            {"assets":[{**original["assets"][0],"digest":None}]},
        ):
            with self.subTest(tampered=tampered):
                with self.assertRaises(UnsafeUpdate):
                    installer.select_preview_release(
                        {**original,**tampered},"0.9.7",RUN-1)

    def test_public_feed_not_found_never_uses_maintainer_cli(self):
        err=urllib.error.HTTPError(installer.PREVIEW_LIST,404,"missing",{},None)
        with (patch.object(installer,"_get_json",side_effect=err),
              patch("dueltrace_private_update_source.read_private_release_metadata")
              as private):
            with self.assertRaises(urllib.error.HTTPError):
                installer.fetch_latest_preview_package()
            private.assert_not_called()

    def test_public_stable_uses_source_sha_in_notes_not_target_commitish(self):
        metadata=release(tag="v0.9.8")
        metadata["prerelease"]=False
        metadata["assets"][0]["name"]=installer.STABLE_ASSET_NAME
        metadata["assets"][0]["browser_download_url"]=(
            public.PUBLIC_UPDATES_WEB+"/releases/download/v0.9.8/"
            +installer.STABLE_ASSET_NAME)
        candidate=installer.select_portable_stable_release(metadata,"0.9.7")
        self.assertEqual(candidate["sha"],SHA)
        self.assertEqual(candidate["version"],"0.9.8")
        self.assertIsNone(candidate["run_id"])


if __name__=="__main__":
    unittest.main()
