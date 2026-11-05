"""Atualizador Preview não assinado: sempre valida origem, hash e build."""
import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
import dueltrace_preview_installer as updater

SHA="a"*40
RUN=41753000001
TAG="preview-v0.8.5-r"+str(RUN)
PAYLOAD=b"trusted-test-zip"


def release(*,tag=TAG,payload=PAYLOAD,sha=SHA):
    return {"tag_name":tag,"draft":False,"prerelease":True,
            "target_commitish":sha,
            "html_url":f"https://github.com/guibatoni/appassist/releases/tag/{tag}",
            "assets":[{
                "name":updater.ASSET_NAME,"size":len(payload),
                "digest":"sha256:"+hashlib.sha256(payload).hexdigest(),
                "browser_download_url":
                    f"https://github.com/guibatoni/appassist/releases/download/{tag}/{updater.ASSET_NAME}"
            }]}


def make_zip(folder: Path, *,version="0.8.5",run_id=RUN,sha=SHA,
             extra=None) -> Path:
    path=folder/"preview.zip"
    with zipfile.ZipFile(path,"w") as z:
        z.writestr("DUELTRACE-WebUI.exe",b"MZ"+b"a"*2048)
        z.writestr("_internal/dueltrace-build.json",
                   json.dumps({"schema":1,"version":version,"run_id":run_id,
                               "head_sha":sha}))
        if extra:
            for key,value in extra.items():
                z.writestr(key,value)
    return path


class PreviewInstallerTests(unittest.TestCase):
    def test_selects_public_preview_from_official_repo(self):
        result=updater.select_preview_release(release(),"0.8.4",None)
        self.assertEqual(result["version"],"0.8.5")
        self.assertEqual(result["run_id"],RUN)
        self.assertEqual(result["sha"],SHA)
        self.assertTrue(result["url"].startswith("https://github.com/guibatoni/appassist/"))

    def test_no_rollback_equal_version_or_ambiguous_same_build(self):
        self.assertIsNone(updater.select_preview_release(release(),"0.9.0",1))
        self.assertIsNone(updater.select_preview_release(release(),"0.8.5",RUN))
        self.assertIsNone(updater.select_preview_release(release(),"0.8.5",None))
        self.assertIsNotNone(updater.select_preview_release(release(),"0.8.5",RUN-1))

    def test_foreign_prerelease_and_unverified_hash_are_rejected(self):
        template=release()
        for malformed in (
            {**template,"html_url":"https://elsewhere.example"},
            {**template,"target_commitish":"not-sha"},
            {**template,"draft":True},
            {**template,"prerelease":False},
            {**template,"assets":[]},
            {**template,"assets":[{**template["assets"][0],"digest":None}]},
            {**template,"assets":[{**template["assets"][0],
                                   "browser_download_url":"https://bad.example"}]},
        ):
            with self.subTest(malformed=malformed),self.assertRaises(updater.UnsafeUpdate):
                updater.select_preview_release(malformed,"0.8.4")

    def test_newest_semver_selected_not_newest_numeric_run(self):
        older=release(tag="preview-v0.8.4-r999999999999")
        newer=release(tag="preview-v0.8.5-r10000")
        selected=updater.fetch_latest_preview_package(
            current_version="0.8.3",fetcher=lambda:[older,newer])
        self.assertEqual(selected["version"],"0.8.5")

    def test_double_digit_minor_release_uses_semver_and_embedded_identity(self):
        older=release(tag="preview-v0.9.9-r999999999999")
        newer=release(tag=f"preview-v0.10.0-r{RUN}")
        selected=updater.fetch_latest_preview_package(
            current_version="0.9.7", fetcher=lambda:[older,newer])
        self.assertEqual(selected["version"], "0.10.0")
        self.assertEqual(selected["run_id"], RUN)
        self.assertIsNone(updater.select_preview_release(older, "0.10.0", 1))
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            source=make_zip(folder, version="0.10.0")
            self.assertTrue(updater.unpack_preview_zip(
                source, folder/"fresh", selected).is_file())
            source=make_zip(folder, version="0.9.9")
            with self.assertRaises(updater.UnsafeUpdate):
                updater.unpack_preview_zip(source, folder/"mismatched", selected)
            self.assertFalse((folder/"mismatched").exists())

    def test_releases_api_is_list_and_invalid_release_is_skipped(self):
        result=updater.fetch_latest_preview_package(
            current_version="0.8.4",fetcher=lambda:[
                {"tag_name":"v0.6.6","prerelease":False},
                {**release(),"target_commitish":"notsha"},
                release()])
        self.assertEqual(result["run_id"],RUN)
        with self.assertRaises(updater.UnsafeUpdate):
            updater.fetch_latest_preview_package(fetcher=lambda:{"bad":"shape"})

    def test_download_verifies_sha256_and_deletes_on_mismatch(self):
        info=updater.select_preview_release(release(),"0.8.4")
        class Response:
            def __init__(self,body):self.body=io.BytesIO(body)
            def read(self,n):return self.body.read(n)
            def geturl(self):return info["url"]
            def __enter__(self):return self
            def __exit__(self,*a):return False
        class Opener:
            def __init__(self,body):self.body=body
            def open(self,request,timeout):return Response(self.body)
        with tempfile.TemporaryDirectory() as td:
            good=Path(td)/"good.zip"
            updater.download_preview_zip(info,good,opener=Opener(PAYLOAD))
            self.assertEqual(good.read_bytes(),PAYLOAD)
            bad=Path(td)/"bad.zip"
            with self.assertRaises(updater.UnsafeUpdate):
                updater.download_preview_zip(info,bad,opener=Opener(b"tampered-data"))
            self.assertFalse(bad.exists())

    def test_unpack_checks_embedded_run_sha_version_and_zip_traversal(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            good=make_zip(base)
            info=updater.select_preview_release(release(),"0.8.4")
            extracted=updater.unpack_preview_zip(good,base/"fresh",info)
            self.assertTrue(extracted.is_file())
            good.unlink()
            changed=make_zip(base,sha="b"*40)
            with self.assertRaises(updater.UnsafeUpdate):
                updater.unpack_preview_zip(changed,base/"wrong",info)
            self.assertFalse((base/"wrong").exists())
            changed.unlink()
            hostile=make_zip(base,extra={"../escape.txt":b"boom"})
            with self.assertRaises(updater.UnsafeUpdate):
                updater.unpack_preview_zip(hostile,base/"evil",info)
            self.assertFalse((base/"escape.txt").exists())

    def test_duplicate_names_not_accepted_even_case_insensitive(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            source=make_zip(base,extra={"_INTERNAL/DuelTrace-Build.json":"x"})
            info=updater.select_preview_release(release(),"0.8.4")
            with self.assertRaises(updater.UnsafeUpdate):
                updater.unpack_preview_zip(source,base/"repeated",info)

    def test_update_requires_executable_and_refuses_existing_backup(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            app=root/"app"
            app.mkdir()
            exe=app/"DUELTRACE-WebUI.exe"
            exe.write_bytes(b"MZ")
            home=root/"user-data"
            home.mkdir()
            backup=root/".app-backup"
            backup.mkdir()
            info=updater.select_preview_release(release(),"0.8.4")
            with self.assertRaises(updater.UnsafeUpdate):
                updater.stage_preview_update(info=info,data_home=home,
                    current_executable=exe,downloader=lambda *a:None,
                    unpacker=lambda *a:None,launcher=lambda *a:None)

    def test_updater_never_replaces_unknown_files_in_install_folder(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            app=base/"DUELTRACE-WebUI"; app.mkdir()
            exe=app/"DUELTRACE-WebUI.exe"; exe.write_bytes(b"MZ")
            (app/"minha-configuracao.json").write_text('{"favoritos":[1]}')
            home=app/"dados-locais"; home.mkdir()
            info=updater.select_preview_release(release(),"0.8.4")
            scripts=[]
            def prepare(_archive,stage,_info):
                stage.mkdir()
                (stage/"DUELTRACE-WebUI.exe").write_bytes(b"MZ")
            result=updater.stage_preview_update(
                info=info,data_home=home,current_executable=exe,
                downloader=lambda *_:None,unpacker=prepare,launcher=scripts.append)
            self.assertTrue(result["started"])
            self.assertTrue((app/"minha-configuracao.json").exists())
            self.assertIn("$managed=@",scripts[0])
            self.assertIn("Move-Item -LiteralPath $target",scripts[0])
            self.assertNotIn("Rename-Item -LiteralPath $old",scripts[0])

    def test_known_backup_can_rotate_for_multiple_updates(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            app=base/"DUELTRACE-WebUI"; app.mkdir()
            exe=app/"DUELTRACE-WebUI.exe"; exe.write_bytes(b"MZ")
            home=base/"data"; home.mkdir()
            backup=base/".DUELTRACE-WebUI-backup"; backup.mkdir()
            (backup/"DUELTRACE-WebUI.exe").write_bytes(b"MZold")
            (backup/"_internal").mkdir()
            info=updater.select_preview_release(release(),"0.8.4")
            scripts=[]
            def prepare(_archive,stage,_info):
                stage.mkdir()
                (stage/"DUELTRACE-WebUI.exe").write_bytes(b"MZ")
            result=updater.stage_preview_update(
                info=info,data_home=home,current_executable=exe,
                downloader=lambda info,where: where.write_bytes(b"zip"),
                unpacker=prepare,launcher=scripts.append)
            self.assertTrue(result["started"])
            self.assertIn("Remove-Item -LiteralPath $backup",scripts[0])
            self.assertTrue(backup.exists()) # backup not destroyed by current process

    def test_install_prepares_and_launcher_receives_wait_then_swap(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            app=root/"app"; app.mkdir()
            exe=app/"DUELTRACE-WebUI.exe"; exe.write_bytes(b"MZ")
            home=root/"data"; home.mkdir()
            info=updater.select_preview_release(release(),"0.8.4")
            scripts=[]
            def fake_download(meta,path):
                path.write_bytes(b"fake-preview")
            def fake_unpack(archive,stage,meta):
                stage.mkdir()
                (stage/"DUELTRACE-WebUI.exe").write_bytes(b"MZ")
                return stage/"DUELTRACE-WebUI.exe"
            result=updater.stage_preview_update(info=info,data_home=home,
                current_executable=exe,downloader=fake_download,
                unpacker=fake_unpack,launcher=scripts.append)
            self.assertTrue(result["started"])
            self.assertFalse(list(home.glob("preview_updates/*.zip")))
            self.assertIn("Wait-Process",scripts[0])
            self.assertIn("Move-Item -LiteralPath $target",scripts[0])
            self.assertIn("foreach ($name in $managed)",scripts[0])
            self.assertNotIn("Rename-Item -LiteralPath $old",scripts[0])
            self.assertIn("Start-Process",scripts[0])
            self.assertTrue(exe.exists())  # processo atual não é alterado imediatamente

    def test_stable_portable_zip_never_requires_authenticode(self):
        version="v0.9.0"
        sha="b"*40
        payload=b"zip-test"
        asset=updater.STABLE_ASSET_NAME
        stable={
            "tag_name":version,"draft":False,"prerelease":False,
            "target_commitish":sha,
            "html_url":f"https://github.com/guibatoni/appassist/releases/tag/{version}",
            "assets":[{
                "name":asset,"size":len(payload),
                "digest":"sha256:"+hashlib.sha256(payload).hexdigest(),
                "browser_download_url":
                    f"https://github.com/guibatoni/appassist/releases/download/{version}/{asset}",
            }],
        }
        info=updater.select_portable_stable_release(stable,"0.8.5")
        self.assertEqual(info["version"],"0.9.0")
        self.assertIsNone(info["run_id"])
        self.assertIsNone(updater.select_portable_stable_release(stable,"0.9.0","stable"))
        self.assertIsNotNone(updater.select_portable_stable_release(stable,"0.9.0","preview"))
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            archive=make_zip(folder,version="0.9.0",run_id=999,sha=sha)
            exe=updater.unpack_preview_zip(archive,folder/"stable",info)
            self.assertTrue(exe.exists())
            self.assertEqual(updater.fetch_portable_stable_package(
                current_version="0.8.5",fetcher=lambda:stable)["sha"],sha)

    def test_stable_portable_zip_rejects_foreign_or_digestless_release(self):
        version="v0.9.0"
        filename=updater.STABLE_ASSET_NAME
        valid={
            "tag_name":version,"draft":False,"prerelease":False,
            "target_commitish":"b"*40,
            "html_url":f"https://github.com/guibatoni/appassist/releases/tag/{version}",
            "assets":[{
                "name":filename,"size":1200,"digest":"sha256:"+"f"*64,
                "browser_download_url":f"https://github.com/guibatoni/appassist/releases/download/{version}/{filename}",
            }],
        }
        for change in (
            {"html_url":"https://elsewhere.example"},
            {"prerelease":True},
            {"target_commitish":"not-a-hash"},
            {"assets":[{**valid["assets"][0],"digest":None}]},
            {"assets":[{**valid["assets"][0],"browser_download_url":"https://evil.example"}]},
        ):
            with self.subTest(change=change),self.assertRaises(updater.UnsafeUpdate):
                updater.select_portable_stable_release({**valid,**change},"0.8.5")
        self.assertIsNone(updater.select_portable_stable_release(
            {**valid,"assets":[]},"0.8.5"))

    def test_no_unsigned_executable_ever_runs_in_test_before_validation(self):
        with tempfile.TemporaryDirectory() as td:
            called=[]
            with patch.object(updater,"stage_preview_update",side_effect=lambda **kw:called.append(kw)):
                latest=updater.install_preview_release(data_home=Path(td),
                    current_version="0.8.5",installed_run_id=RUN,
                    fetcher=lambda:[release()])
            self.assertEqual(latest["started"],False)
            self.assertFalse(called)


if __name__=="__main__":
    unittest.main()
