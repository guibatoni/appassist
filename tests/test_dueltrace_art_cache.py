"""Evita releituras repetidas de imagens após tentativa de arte não suportada."""
from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))

from auto_mods import ART_PARSER_REVISION, DISC_METADATA_REVISION, ModCatalog, atomic_json


class ArtAttemptCacheTests(unittest.TestCase):
    def test_unavailable_art_is_cached_but_reanalysis_is_explicit(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            rom=home/"mod.iso"
            rom.write_bytes(b"\x42"*100_002)
            sha=hashlib.sha256(rom.read_bytes()).hexdigest()
            scan=home/"analises"/"mod"
            profile_path=home/"profiles"/sha[:16]/"profile.json"
            atomic_json(scan/"relatorio.json",{
                "art_requested": True,
                "art_parser_revision": ART_PARSER_REVISION,
                "artes_extraidas":0,
                "artes_obs":"Formato de artes não reconhecido",
            })
            profile={
                "rom_sha256":sha,
                "scan_result_dir":str(scan),
                "disc_metadata_revision":DISC_METADATA_REVISION,
                "supported_features":{"art":False},
                "verified":{"cartas":"pendente"},
            }
            atomic_json(profile_path,profile)
            old={
                "source_path":str(rom.resolve()),
                "file_name":rom.name,
                "sha256":sha,
                "profile_path":str(profile_path.resolve()),
                "size":rom.stat().st_size,
                "mtime_ns":rom.stat().st_mtime_ns,
                "effects_manifest_signature":[0,0],
                "level":"desconhecido",
            }
            catalog=ModCatalog(home)
            atomic_json(catalog.registry_file,{"schema":1,"entries":[old]})
            with patch("auto_mods.import_rom",side_effect=AssertionError(
                "cache negativo deveria impedir leitura")):
                same=catalog.analyse(rom,with_art=True)
            self.assertEqual(same["sha256"],sha)
            with patch("auto_mods.import_rom",return_value=(profile,profile_path)) as reader:
                refreshed=catalog.analyse(rom,with_art=True,force=True)
                reader.assert_called_once()
                self.assertEqual(refreshed["sha256"],sha)

    def test_parser_upgrade_retries_failed_art_extraction(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            rom=home/"mod.bin"
            rom.write_bytes(b"A"*100_002)
            sha=hashlib.sha256(rom.read_bytes()).hexdigest()
            scan=home/"analises"/"mod"
            profile_path=home/"profiles"/sha[:16]/"profile.json"
            atomic_json(scan/"relatorio.json",{
                "art_requested":True,
                "art_parser_revision":ART_PARSER_REVISION-1,
                "artes_extraidas":0,
            })
            profile={"rom_sha256":sha,"scan_result_dir":str(scan),
                     "supported_features":{"art":False}}
            atomic_json(profile_path,profile)
            old={
                "source_path":str(rom.resolve()),
                "file_name":rom.name,
                "sha256":sha,
                "profile_path":str(profile_path.resolve()),
                "size":rom.stat().st_size,
                "mtime_ns":rom.stat().st_mtime_ns,
                "effects_manifest_signature":[0,0],
            }
            catalog=ModCatalog(home)
            atomic_json(catalog.registry_file,{"schema":1,"entries":[old]})
            with patch("auto_mods.import_rom",return_value=(profile,profile_path)) as reader:
                catalog.analyse(rom,with_art=True)
                reader.assert_called_once()


if __name__=="__main__":
    unittest.main()
