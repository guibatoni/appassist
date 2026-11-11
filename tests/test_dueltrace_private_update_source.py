"""Private Windows Preview updater: owner-authenticated, no embedded secrets.

Release origin/size/digest + embedded build identity checks still apply;
the updater never auto-installs or changes the original install folder here.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))

import dueltrace_private_update_source as cli
import dueltrace_preview_installer as updater
import dueltrace_update_checker as checker

SHA="a"*40
RUN=42904794555
TAG=f"preview-v0.9.7-r{RUN}"
ASSET=b"private-test-zip-bytes"


def preview_release(asset=ASSET):
    return {
        "draft":False, "prerelease":True, "tag_name":TAG,
        "target_commitish":"main",
        "body":f"Build {RUN} | Commit {SHA} | SHA-256 ZIP: {hashlib.sha256(asset).hexdigest()}",
        "html_url":f"https://github.com/guibatoni/dueltrace-releases/releases/tag/{TAG}",
        "assets":[{"name":updater.ASSET_NAME,
            "size":len(asset),
            "digest":"sha256:"+hashlib.sha256(asset).hexdigest(),
            "browser_download_url":
                f"https://github.com/guibatoni/dueltrace-releases/releases/download/{TAG}/{updater.ASSET_NAME}"}],
    }


def http_error(code):
    return urllib.error.HTTPError(
        "https://api.github.com/repos/guibatoni/appassist/releases?per_page=30",
        code,"private or unavailable",{},None)


class PrivateUpdatesTests(unittest.TestCase):
    def test_customer_preview_is_anonymous_and_never_uses_private_cli(self):
        with (patch.object(updater,"_get_json",return_value=[preview_release()]) as public,
              patch.object(cli,"read_private_release_metadata") as private):
            found=updater.fetch_latest_preview_package(
                current_version="0.9.7",installed_run_id=RUN-1)
        self.assertNotIn("transport",found)
        self.assertEqual(found["version"],"0.9.7")
        self.assertEqual(found["run_id"],RUN)
        self.assertEqual(found["sha"],SHA)
        self.assertEqual(found["sha256"],hashlib.sha256(ASSET).hexdigest())
        public.assert_called_once_with(updater.PREVIEW_LIST,list)
        private.assert_not_called()

    def test_missing_public_release_never_falls_back_to_private_cli(self):
        for code in (401,403,404,500):
            with (patch.object(updater,"_get_json",side_effect=http_error(code)),
                  patch.object(cli,"read_private_release_metadata") as private):
                with self.assertRaises(urllib.error.HTTPError):
                    updater.fetch_latest_preview_package()
                private.assert_not_called()
        forged=preview_release()
        forged["html_url"]="https://attacker.example/release"
        with patch.object(updater,"_get_json",return_value=[forged]):
            selected=updater.fetch_latest_preview_package(
                current_version="0.9.7",installed_run_id=RUN-1)
        self.assertIsNone(selected)

    def test_stable_release_is_discovered_anonymously(self):
        tag="v0.9.8"
        release={
            "draft":False,"prerelease":False,"tag_name":tag,
            "html_url":f"https://github.com/guibatoni/dueltrace-releases/releases/tag/{tag}",
            "target_commitish":"main",
            "body":f"Build {RUN} | Commit {SHA} | SHA-256 ZIP: {hashlib.sha256(ASSET).hexdigest()}",
            "assets":[{
                "name":updater.STABLE_ASSET_NAME,
                "size":len(ASSET),
                "digest":"sha256:"+hashlib.sha256(ASSET).hexdigest(),
                "browser_download_url":
                    f"https://github.com/guibatoni/dueltrace-releases/releases/download/{tag}/{updater.STABLE_ASSET_NAME}",
            }],
        }
        with (patch.object(checker,"fetch_stable_release",return_value=release),
              patch.object(cli,"read_private_release_metadata") as private):
            selected=updater.fetch_portable_stable_package(
                current_version="0.9.7")
        self.assertEqual(selected["version"],"0.9.8")
        self.assertEqual(selected["sha256"],hashlib.sha256(ASSET).hexdigest())
        self.assertNotIn("transport",selected)
        private.assert_not_called()

    def test_private_download_is_integrity_checked_and_atomic(self):
        with tempfile.TemporaryDirectory() as td:
            destination=Path(td)/"new.zip"
            def fake_cli(args,timeout):
                self.assertEqual(args[:2],["release","download"])
                self.assertEqual(args[2],TAG)
                self.assertEqual(args[args.index("--repo")+1],cli.REPO)
                self.assertEqual(args[args.index("--pattern")+1],cli.ZIP_ASSET)
                path=Path(args[args.index("--output")+1])
                self.assertFalse(path.exists())
                path.write_bytes(ASSET)
                return b""
            with (patch.object(cli,"_check_version"),
                  patch.object(cli,"_run",side_effect=fake_cli)):
                result=cli.download_private_zip(
                    TAG,cli.ZIP_ASSET,destination,
                    sha256=hashlib.sha256(ASSET).hexdigest(),
                    expected_size=len(ASSET))
            self.assertEqual(result,destination)
            self.assertEqual(destination.read_bytes(),ASSET)
            self.assertEqual(list(Path(td).glob(".dueltrace-*.zip")),[])

    def test_private_download_rejects_tampering_without_leaving_partial_file(self):
        with tempfile.TemporaryDirectory() as td:
            destination=Path(td)/"new.zip"
            def malicious(args,timeout):
                Path(args[args.index("--output")+1]).write_bytes(ASSET)
                return b""
            with (patch.object(cli,"_check_version"),
                  patch.object(cli,"_run",side_effect=malicious)):
                with self.assertRaises(cli.PrivateUpdateUnavailable):
                    cli.download_private_zip(TAG,cli.ZIP_ASSET,destination,
                        sha256="0"*64,expected_size=len(ASSET))
            self.assertFalse(destination.exists())
            self.assertEqual(list(Path(td).glob(".dueltrace-*.zip")),[])

    def test_public_download_still_uses_existing_https_path(self):
        info=updater.select_preview_release(preview_release(), "0.9.7", RUN-1)
        self.assertNotIn("transport",info)
        self.assertTrue(info["url"].startswith("https://github.com/"))
        with patch.object(cli,"download_private_zip") as download:
            self.assertNotIn("transport",info)
            self.assertFalse(download.called)

    def test_private_source_rejects_unauthenticated_or_outdated_cli(self):
        with patch.object(cli,"_run",return_value=b"gh version 2.101.0 (old)"):
            with self.assertRaisesRegex(cli.PrivateUpdateUnavailable,"2.102"):
                cli._check_version()
        with patch.object(cli,"_run",return_value=b"gh version 2.102.0 (safe)"):
            cli._check_version()
        with (patch.object(cli.shutil,"which",return_value=None),
              patch.dict(cli.os.environ,{
                  "ProgramFiles":"","ProgramW6432":"","LOCALAPPDATA":""})):
            with self.assertRaises(cli.PrivateUpdateUnavailable):
                cli._gh_path()

    def test_windows_installed_cli_detected_when_explorer_path_is_stale(self):
        # A user can start DUELTRACE from Windows Explorer after installing
        # GitHub CLI, but Explorer might keep an older PATH snapshot.
        if cli.os.name!="nt":
            self.skipTest("Windows installer paths are Windows-only")
        with tempfile.TemporaryDirectory() as root:
            exe=Path(root)/"GitHub CLI"/"gh.exe"
            exe.parent.mkdir()
            exe.write_bytes(b"MZ")
            with (patch.object(cli.shutil,"which",return_value=None),
                  patch.dict(cli.os.environ,{
                      "ProgramFiles":root,"ProgramW6432":"","LOCALAPPDATA":""})):
                self.assertEqual(cli._gh_path(),str(exe))

    def test_missing_cli_error_is_precise_not_hidden_as_generic_network_error(self):
        with patch.object(cli,"_gh_path",side_effect=cli.PrivateUpdateUnavailable(
                "GitHub CLI não encontrado. Execute gh auth login.")):
            with self.assertRaisesRegex(cli.PrivateUpdateUnavailable,
                                         "GitHub CLI não encontrado"):
                cli._run(["version"],timeout=5)

    def test_gh_cli_process_is_noninteractive_and_does_not_log_secrets(self):
        fake=subprocess.CompletedProcess(
            args=["gh"],returncode=1,stdout=b"",stderr=b"some token")
        with (patch.object(cli.shutil,"which",return_value="C:/Program Files/GitHub CLI/gh.exe"),
              patch.object(cli.subprocess,"run",return_value=fake) as proc):
            with self.assertRaises(cli.PrivateUpdateUnavailable) as result:
                cli._run(["version"],timeout=6)
        self.assertNotIn("token",str(result.exception).lower())
        args,kwargs=proc.call_args
        self.assertFalse(kwargs["shell"])
        self.assertEqual(kwargs["env"]["GH_PROMPT_DISABLED"],"1")
        self.assertEqual(kwargs["env"]["GH_HOST"],"github.com")
        self.assertNotIn("password",str(args).lower())

    def test_same_button_keeps_current_folder_restart_and_rollback(self):
        ui=(ROOT/"web/components/shell/update-checker.tsx").read_text(encoding="utf-8")
        staged=(ROOT/"scanner/dueltrace_preview_installer.py").read_text(encoding="utf-8")
        self.assertIn('aria-label="Atualizar agora"',ui)
        self.assertIn("api.install_preview_update()",ui)
        self.assertIn("api.install_portable_update()",ui)
        self.assertNotIn("gh auth login",ui)
        self.assertNotIn("api.gh_auth(",ui)
        self.assertNotIn("subprocess.run(",ui)
        self.assertIn("Move-Item -LiteralPath $target",staged)
        self.assertIn("Start-Process -FilePath $exe -WorkingDirectory $old -PassThru",staged)
        self.assertIn("Rollback concluído;",staged)
        self.assertIn("sha256",staged)
        self.assertIn("_internal",staged)


if __name__=="__main__":
    unittest.main()
