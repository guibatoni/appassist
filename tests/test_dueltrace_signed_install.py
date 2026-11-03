"""Instalador de release: testes offline; nenhum binário é executado."""
import hashlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
import dueltrace_signed_install as updater

EDITOR="CN=Batoni Dev Verified, O=Verified Publisher, C=BR"


def release(version="v0.8.0", payload=b"MZ-exemplo-seguro"):
    filename=f"DUELTRACE-Setup-{version}.exe"
    return {
        "tag_name":version, "draft":False, "prerelease":False,
        "html_url":f"https://github.com/guibatoni/appassist/releases/tag/{version}",
        "assets":[{
            "name":filename, "size":len(payload),
            "digest":"sha256:"+hashlib.sha256(payload).hexdigest(),
            "browser_download_url":
                f"https://github.com/guibatoni/appassist/releases/download/{version}/{filename}",
        }]
    }


class SignedUpdaterTests(unittest.TestCase):
    def test_no_bypass_without_verified_publisher(self):
        self.assertFalse(updater.trusted_installer_ready(publisher=""))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(updater.UnsafeUpdate):
                updater.install_new_release(
                    data_home=Path(tmp),release_fetcher=lambda:release(),
                    publisher="",signer=lambda path:EDITOR)

    def test_selects_only_newer_official_signed_release_asset(self):
        c=updater.select_signed_installer(release(),"0.7.5")
        self.assertEqual(c["version"],"v0.8.0")
        self.assertTrue(c["url"].startswith("https://github.com/guibatoni/appassist/"))
        self.assertIsNone(updater.select_signed_installer(release(),"0.9.0"))
        for data in [
            {**release(),"prerelease":True},
            {**release(),"html_url":"https://evil.example"},
            {**release(),"assets":[]},
            {**release(),"assets":[{**release()["assets"][0],"digest":None}]},
            {**release(),"assets":[{**release()["assets"][0],
                "browser_download_url":"https://evil.example/virus.exe"}]},
        ]:
            with self.subTest(item=data):
                with self.assertRaises(updater.UnsafeUpdate):
                    updater.select_signed_installer(data,"0.7.5")

    def test_hash_is_checked_before_installer_signature(self):
        payload=b"MZ-real-file-for-test"
        info=updater.select_signed_installer(release(payload=payload),"0.7.5")
        class Response:
            def __init__(self,body):
                self.body=io.BytesIO(body)
            def read(self,amount): return self.body.read(amount)
            def geturl(self):return info["url"]
            def __enter__(self):return self
            def __exit__(self,*a):return False
        class Opener:
            def __init__(self,body):self.body=body
            def open(self,request,timeout):return Response(self.body)
        with tempfile.TemporaryDirectory() as td:
            good=Path(td)/"good.exe"
            updater._download_release(info,good,opener=Opener(payload))
            self.assertEqual(good.read_bytes(),payload)
            bad=Path(td)/"bad.exe"
            with self.assertRaises(updater.UnsafeUpdate):
                updater._download_release(info,bad,opener=Opener(payload[:-1]+b"x"))
            self.assertFalse(bad.exists())

    def test_installer_starts_only_after_matching_authenticode(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            actions=[]
            def downloader(info,where):
                where.write_bytes(b"MZ-staged-installer")
            def launcher(where):
                actions.append(where.name)
            with patch.object(updater,"trusted_installer_ready",return_value=True):
                outcome=updater.install_new_release(
                    data_home=folder,current_version="0.7.5",
                    release_fetcher=lambda:release(),
                    publisher=EDITOR,signer=lambda p:EDITOR,
                    downloader=downloader,launcher=launcher)
                self.assertTrue(outcome["started"])
                self.assertEqual(actions,["DUELTRACE-Setup-v0.8.0.exe"])
                with self.assertRaises(updater.UnsafeUpdate):
                    updater.install_new_release(
                        data_home=folder,current_version="0.7.5",
                        release_fetcher=lambda:release(),publisher=EDITOR,
                        signer=lambda p:"CN=IMPOSTOR",
                        downloader=downloader,launcher=launcher)
            self.assertFalse((folder/"trusted_updates"/"DUELTRACE-Setup-v0.8.0.exe").exists())

    def test_no_install_on_equal_or_older_version(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(updater,"trusted_installer_ready",return_value=True):
                result=updater.install_new_release(
                    data_home=Path(td),current_version="0.8.0",
                    release_fetcher=lambda:release(),publisher=EDITOR,
                    downloader=lambda *args: self.fail("Não pode baixar"))
        self.assertFalse(result["started"])


if __name__=="__main__":
    unittest.main()
