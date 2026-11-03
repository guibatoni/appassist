"""Evita releituras repetidas de imagens após tentativa de arte não suportada."""
from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))

from auto_mods import ART_PARSER_REVISION, ModCatalog, atomic_json


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

    def test_full_wa_rescan_keeps_manual_and_same_sha_structural_fusions(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            rom=home/"custom.bin"
            rom.write_bytes(b"R"*100_003)
            digest=hashlib.sha256(rom.read_bytes()).hexdigest()
            profile_path=home/"profiles"/digest[:16]/"profile.json"
            fingerprint="f"*64
            manual={"a":1,"b":2,"result":3,
                    "validation":"observada_manualmente_no_jogo"}
            structural={"a":4,"b":5,"result":6,
                        "validation":"extraida_sete_bancos_consistentes",
                        "fusion_candidate_fingerprint":fingerprint}
            old_profile={
                "rom_sha256":digest,
                "verified":{"cartas":"verificado","fusoes":"extraidas_sete_bancos_nao_testadas_no_jogo"},
                "supported_features":{"cards":True,"fusions":True,"art":True},
                "fusion_recipes":[manual,structural,
                    {"a":9,"b":10,"result":11,"validation":"sem_origem"}],
                "fusion_review":{"candidate_fingerprint":fingerprint},
            }
            atomic_json(profile_path,old_profile)
            catalog=ModCatalog(home)
            old={
                "source_path":str(rom.resolve()),"file_name":rom.name,
                "sha256":digest,"profile_path":str(profile_path.resolve()),
                "size":rom.stat().st_size,"mtime_ns":rom.stat().st_mtime_ns,
                "effects_manifest_signature":[0,0],
            }
            atomic_json(catalog.registry_file,{"schema":1,"entries":[old]})
            incoming={
                "rom_sha256":digest,
                "verified":{"cartas":"verificado","fusoes":"não_extraídas"},
                "supported_features":{"cards":True,"fusions":False,"art":True},
                "fusion_recipes":[],
            }
            def fake_import(*args,**kwargs):
                atomic_json(profile_path,incoming)
                return incoming,profile_path
            with patch("auto_mods.import_rom",side_effect=fake_import):
                refreshed=catalog.analyse(rom,with_art=True,force=True)
            saved=catalog.profile_for(refreshed)
            self.assertEqual(saved["fusion_recipes"],[manual,structural])
            self.assertEqual(saved["fusion_review"]["structurally_validated"],1)
            self.assertEqual(saved["fusion_review"]["in_game_individually_verified"],1)
            self.assertTrue(saved["supported_features"]["fusions"])



if __name__=="__main__":
    unittest.main()
