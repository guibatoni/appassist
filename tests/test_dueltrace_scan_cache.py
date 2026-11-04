"""Cache geral independe da opção de artes e invalida parsers antigos uma vez."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))

import scanner_multiiso
from auto_mods import ModCatalog, DirectoryMonitor, atomic_json, SCAN_PARSER_REVISION


class ScanParserCacheTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home=Path(temp.name)
        self.rom=self.home/"same.iso"
        self.rom.write_bytes(b"S"*100_002)
        self.sha=hashlib.sha256(self.rom.read_bytes()).hexdigest()
        self.profile_path=self.home/"profiles"/self.sha[:16]/"profile.json"
        self.profile={"rom_sha256":self.sha,"supported_features":{},"verified":{}}
        atomic_json(self.profile_path,self.profile)
        stat=self.rom.stat()
        self.entry={
            "source_path":str(self.rom),"file_name":self.rom.name,
            "sha256":self.sha,"profile_path":str(self.profile_path),
            "size":stat.st_size,"mtime_ns":stat.st_mtime_ns,
            "effects_manifest_signature":[0,0],
            "scan_parser_revision":SCAN_PARSER_REVISION-1,"approved":True,
        }
        self.catalog=ModCatalog(self.home)
        self._save_entry()

    def _save_entry(self):
        atomic_json(self.catalog.registry_file,{"schema":1,"entries":[self.entry]})

    def _import(self,*args,**kwargs):
        # The real importer hashes before parsing; count this I/O explicitly.
        self.assertEqual(scanner_multiiso.sha256(self.rom),self.sha)
        return self.profile,self.profile_path

    def test_no_art_parser_upgrade_runs_once_then_reuses_without_hashing(self):
        with patch("auto_mods.import_rom",side_effect=self._import) as importer, \
                patch("scanner_multiiso.sha256",wraps=scanner_multiiso.sha256) as hasher:
            first=self.catalog.analyse(self.rom,with_art=False)
            for _ in range(3):
                self.assertEqual(self.catalog.analyse(self.rom,with_art=False),first)
            importer.assert_called_once()
            hasher.assert_called_once_with(self.rom)
        self.assertEqual(first["scan_parser_revision"],SCAN_PARSER_REVISION)
        self.assertTrue(first["approved"])

    def test_revisionless_legacy_cache_is_refreshed_once(self):
        self.entry.pop("scan_parser_revision")
        self._save_entry()
        with patch("auto_mods.import_rom",side_effect=self._import) as importer:
            self.catalog.analyse(self.rom)
            self.catalog.analyse(self.rom)
            importer.assert_called_once()

    def test_same_revision_does_not_read_image_but_missing_profile_refreshes(self):
        self.entry["scan_parser_revision"]=SCAN_PARSER_REVISION
        self._save_entry()
        with patch("auto_mods.import_rom",side_effect=AssertionError("cache hit must not parse")), \
                patch("scanner_multiiso.sha256",side_effect=AssertionError("cache hit must not hash")):
            self.assertEqual(self.catalog.analyse(self.rom),self.entry)
            self.assertTrue(self.catalog.cached_analysis_is_current(self.rom))
        self.profile_path.unlink()
        with patch("auto_mods.import_rom",side_effect=self._import) as importer:
            self.catalog.analyse(self.rom)
            importer.assert_called_once()

    def test_monitor_enqueues_old_parser_instead_of_skipping_same_mtime(self):
        monitor=DirectoryMonitor(self.home,self.catalog,quiet_seconds=1)
        stop=Mock()
        stop.is_set.side_effect=[False,False,True]
        monitor._stop=stop
        with patch("auto_mods.time.monotonic",side_effect=[0,5]):
            monitor._scan()
        self.assertEqual(monitor._work.get_nowait(),self.rom)
        self.assertTrue(monitor._work.empty())

    def test_scanner_records_revision_even_without_art_or_supported_layout(self):
        with patch("scanner_multiiso.Disc",side_effect=ValueError("layout sintético incompatível")):
            result=scanner_multiiso.process(
                self.rom,self.home/"output",with_art=False,digest=self.sha)
        self.assertFalse(result["art_requested"])
        self.assertEqual(result["scan_parser_revision"],SCAN_PARSER_REVISION)
        saved=json.loads((Path(result["resultado_dir"])/"relatorio.json").read_text())
        self.assertEqual(saved["scan_parser_revision"],SCAN_PARSER_REVISION)


if __name__=="__main__":
    unittest.main()
