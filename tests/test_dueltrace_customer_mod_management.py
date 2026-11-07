"""Customer-facing ISO library operations: local alias and safe unregister."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from auto_mods import ModCatalog,atomic_json
from dueltrace_web_bridge import DueltraceWebBridge
from dueltrace_web_security import ProtectedDesktopApi
from test_dueltrace_drops import fake_profile


class ModNicknamesAndTrashTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home=Path(temp.name)
        self.sha="a"*64
        self.iso=self.home/"Original Game Name.iso"
        self.iso.write_bytes(b"test-only-synthetic-data"*7000)
        self.profile=fake_profile(self.sha)
        folder=self.home/"profiles"/self.sha[:16]
        folder.mkdir(parents=True,exist_ok=True)
        self.profile_path=folder/"profile.json"
        atomic_json(self.profile_path,self.profile)
        self.catalog=ModCatalog(self.home)
        self.entry={
            "sha256":self.sha,
            "file_name":self.iso.name,
            "source_path":str(self.iso),
            "profile_path":str(self.profile_path),
            "level":"parcial_revisar",
            "approved":True,
        }
        atomic_json(self.catalog.registry_file,{"schema":1,"entries":[self.entry]})
        atomic_json(self.catalog.active_file,{"sha256":self.sha})
        self.bridge=DueltraceWebBridge(self.catalog)
        self.api=ProtectedDesktopApi(self.bridge,"t"*64)

    def test_nickname_changes_app_only_and_preserves_on_rescan(self):
        with self.assertRaises(PermissionError):
            self.api.rename_mod("invalid",self.sha,"Meu Mod")
        result=self.api.rename_mod("t"*64,self.sha,"  GOG    favorito  ")
        self.assertEqual(result["displayName"],"GOG favorito")
        self.assertEqual(self.catalog.list()[0]["file_name"],self.iso.name)
        self.assertEqual(self.bridge.get_state()["activeName"],"GOG favorito")
        self.assertTrue(self.iso.exists())
        self.assertEqual(self.iso.name,"Original Game Name.iso")
        with patch("auto_mods.import_rom",return_value=(self.profile,self.profile_path)):
            updated=self.catalog.analyse(self.iso,force=True)
        self.assertEqual(updated["display_name"],"GOG favorito")
        self.assertEqual(updated["file_name"],self.iso.name)
        self.assertEqual(self.bridge.get_state()["mods"][0]["name"],"GOG favorito")

    def test_trash_never_deletes_iso_or_analysis_and_clears_active(self):
        with self.assertRaises(PermissionError):
            self.api.remove_mod("invalid",self.sha)
        self.api.rename_mod("t"*64,self.sha,"Minha ISO")
        result=self.api.remove_mod("t"*64,self.sha)
        self.assertTrue(result["removed"])
        self.assertTrue(result["wasActive"])
        self.assertTrue(result["sourceFilePreserved"])
        self.assertTrue(self.iso.is_file())
        self.assertTrue(self.profile_path.is_file())
        self.assertEqual(self.catalog.list(),[])
        self.assertIsNone(self.catalog.current())
        state=self.api.get_state("t"*64)
        self.assertIsNone(state["activeSha"])
        self.assertIsNone(state["activeName"])
        self.assertEqual(state["mods"],[])
        with self.assertRaises(ValueError):
            self.api.remove_mod("t"*64,self.sha)

    def test_invalid_nickname_is_rejected_without_changing_registry(self):
        for value in ("", " "*5, "x"*73, "bad\nname", None, 9):
            with self.subTest(value=value),self.assertRaises(ValueError):
                self.api.rename_mod("t"*64,self.sha,value)
        self.assertNotIn("display_name",self.catalog.list()[0])
        self.assertTrue(self.iso.exists())

    def test_removing_non_active_mod_leaves_active_mod_unchanged(self):
        other="b"*64
        entry={**self.entry,"sha256":other}
        atomic_json(self.catalog.registry_file,{"schema":1,
                   "entries":[self.entry,entry]})
        result=self.api.remove_mod("t"*64,other)
        self.assertFalse(result["wasActive"])
        self.assertEqual(self.catalog.current()["sha256"],self.sha)
        self.assertEqual(len(self.catalog.list()),1)


if __name__=="__main__":
    unittest.main()
