"""Testes do motor de investigação local e dos quatro separadores públicos."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scanner"))

from auto_mods import ModCatalog, atomic_json
from dueltrace_desktop import PAGES, USER_PAGES, DueltraceDesktop
from dueltrace_intelligence import (
    MultiModIntelligence, inventory_from_profile, ollama_status)
from ia_local import minimal_evidence


class IntelligenceTests(unittest.TestCase):
    def test_public_navigation_only_four_pages(self):
        self.assertEqual([key for _, key in USER_PAGES],
                         ["inicio", "mods", "cartas", "fusoes"])
        self.assertEqual(len(PAGES), 7)
        self.assertTrue(callable(DueltraceDesktop._page_mods))

    def test_inventory_uses_extracted_metadata_not_roman_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            scan = home / "analises" / "demo"
            scan.mkdir(parents=True)
            atomic_json(scan / "relatorio.json", {
                "arquivos_discos": [
                    {"nome": "SLUS_000.01", "lba": 3, "tamanho": 4096},
                    {"nome": "WA_MRG.MRG", "lba": 8, "tamanho": 10000},
                ]
            })
            profile = {
                "scan_result_dir": str(scan),
                "supported_features": {"cards": True, "drops": True,
                                       "effects": True, "art": False},
                "cards": [{"id": 10, "effect_text": "Efeito declarado",
                           "effect_source": "manifesto local"}],
                "drops": [{"card_id": 10}],
                "verified": {"cartas": "verificado"},
            }
            inv = inventory_from_profile(profile)
            self.assertEqual(inv["iso_files_indexed"], 2)
            self.assertEqual(inv["cards"], 1)
            self.assertEqual(inv["drop_entries"], 1)
            self.assertEqual(inv["effects_with_provenance"], 1)
            report = minimal_evidence({
                "file": "demo.iso", "features": profile["verified"],
                "inventory": inv, "candidates": {},
            })
            self.assertEqual(report["catalog"]["drop_entries"], 1)
            self.assertEqual(report["file_inventory_sample"][0]["name"], "SLUS_000.01")
            self.assertNotIn("art_path", report)

    def test_ollama_not_required_and_model_is_verified(self):
        with patch("dueltrace_intelligence.urlopen", side_effect=OSError("offline")):
            self.assertEqual(ollama_status()["state"], "ollama_indisponivel")
        fake = Mock()
        fake.status = 200
        fake.read.return_value = b'{"models": [{"name":"qwen2.5:3b"}]}'
        fake.__enter__ = Mock(return_value=fake)
        fake.__exit__ = Mock(return_value=False)
        with patch("dueltrace_intelligence.urlopen", return_value=fake):
            self.assertTrue(ollama_status()["available"])
            self.assertEqual(ollama_status("other:latest")["state"], "modelo_ausente")

    def test_verified_iso_auto_probes_seven_fusions_once_per_file_version(self):
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp)
            image=home/"custom.iso"
            image.write_bytes(b"safe synthetic data")
            stat=image.stat()
            sha="d"*64
            profile_path=home/"profiles"/"custom"/"profile.json"
            atomic_json(profile_path,{
                "rom_sha256":sha,
                "scan_result_dir":str(home/"analises"/"custom"),
                "cards":[{"id":i,"name":str(i)} for i in range(1,723)],
                "verified":{"cartas":"verificado"},
                "supported_features":{"cards":True},
            })
            catalog=ModCatalog(home)
            atomic_json(catalog.registry_file,{"schema":1,"entries":[{
                "source_path":str(image.resolve()),
                "file_name":"custom.iso","sha256":sha,
                "profile_path":str(profile_path),
                "size":stat.st_size,"mtime_ns":stat.st_mtime_ns,
                "level":"parcial_revisar",
            }]})
            fake={"valid_banks":7,"matching_banks":7,
                  "divergent_banks":False,"bank_conflicts":0,
                  "candidates":[],"banks":[]}
            with (patch("dueltrace_intelligence.investigate",return_value={
                    "file":"custom.iso","hash_rom":sha,"features":{},
                    "candidates":{},"uncertainties":[],"evidence":[]}),
                  patch("dueltrace_intelligence.audit_effect_sources",
                        return_value={"status":"sem_prova","candidate_files":[]}),
                  patch("extrator_fusoes.analyze_fusion_banks",
                        return_value=fake) as probe,
                  patch("dueltrace_intelligence.import_structural_fusions",
                        return_value={"status":"importadas","count":80}) as importer):
                engine=MultiModIntelligence(catalog)
                one=engine.inspect(image,use_ollama=False)
                two=engine.inspect(image,use_ollama=False)
            self.assertEqual(one["fusions"]["status"],"importadas")
            self.assertEqual(two["state"],"cache")
            probe.assert_called_once()
            self.assertEqual(importer.call_count,2)
            saved=home/"investigacoes"/(sha+".fusoes.json")
            self.assertTrue(saved.exists())
            self.assertEqual(json.loads(saved.read_text())["rom_sha256"],sha)
            self.assertTrue((home/"investigacoes"/(sha+".fusoes-probe-status.json")).exists())

    def test_unrecognized_fusion_format_is_negative_cached_not_promoted(self):
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp)
            image=home/"unsupported.iso"
            image.write_bytes(b"synthetic")
            stat=image.stat()
            sha="c"*64
            profile_path=home/"profiles"/"unknown"/"profile.json"
            atomic_json(profile_path,{
                "rom_sha256":sha,
                "cards":[{"id":i,"name":str(i)} for i in range(1,723)],
                "verified":{"cartas":"verificado"},
                "supported_features":{"cards":True,"fusions":False},
            })
            catalog=ModCatalog(home)
            atomic_json(catalog.registry_file,{"schema":1,"entries":[{
                "source_path":str(image.resolve()),
                "file_name":"unsupported.iso","sha256":sha,
                "profile_path":str(profile_path),
                "size":stat.st_size,"mtime_ns":stat.st_mtime_ns,
            }]})
            with (patch("dueltrace_intelligence.investigate",return_value={
                    "file":"unsupported.iso","hash_rom":sha,"features":{},
                    "candidates":{},"uncertainties":[],"evidence":[]}),
                  patch("dueltrace_intelligence.audit_effect_sources",
                        return_value={"status":"sem_prova","candidate_files":[]}),
                  patch("extrator_fusoes.analyze_fusion_banks",
                        side_effect=ValueError("formato não identificado")) as probe):
                engine=MultiModIntelligence(catalog)
                first=engine.inspect(image,use_ollama=False)
                second=engine.inspect(image,use_ollama=False)
            probe.assert_called_once()
            self.assertEqual(first["fusions"]["count"],0)
            self.assertEqual(second["fusions"]["count"],0)
            self.assertFalse((home/"investigacoes"/(sha+".fusoes.json")).exists())

    def test_seven_consistent_banks_with_conflicts_are_preserved_only_locally(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp)
            image=home/"rising.iso"
            image.write_bytes(b"synthetic")
            sha="e"*64
            profile_path=home/"profiles"/"synthetic"/"profile.json"
            atomic_json(profile_path,{
                "rom_sha256":sha,"cards":[{"id":i} for i in range(1,723)],
                "verified":{"cartas":"verificado"},
                "supported_features":{"cards":True,"fusions":False},
            })
            st=image.stat()
            catalog=ModCatalog(home)
            atomic_json(catalog.registry_file,{"schema":1,"entries":[{
                "sha256":sha,"file_name":image.name,
                "source_path":str(image.resolve()),
                "profile_path":str(profile_path),
                "size":st.st_size,"mtime_ns":st.st_mtime_ns,
            }]})
            fake={
                "valid_banks":7,"matching_banks":7,
                "divergent_banks":False,"bank_conflicts":6,
                "candidate_count":5555,
                "unique_unordered_pairs_without_conflict":5549,
                "unordered_pairs_with_conflicting_results":3,
                "candidates":[{"a":62,"b":66,"result":68},
                              {"a":66,"b":62,"result":69}],
                "banks":[{"status":"decodificado"} for _ in range(7)],
            }
            with (patch("dueltrace_intelligence.investigate",return_value={
                    "file":image.name,"hash_rom":sha,"features":{},
                    "candidates":{},"uncertainties":[],"evidence":[]}),
                  patch("dueltrace_intelligence.audit_effect_sources",
                        return_value={"status":"sem_prova","candidate_files":[]}),
                  patch("extrator_fusoes.analyze_fusion_banks",
                        return_value=fake) as probe,
                  patch("dueltrace_intelligence.import_structural_fusions") as importer):
                engine=MultiModIntelligence(catalog)
                first=engine.inspect(image,use_ollama=False)
                second=engine.inspect(image,use_ollama=False)
            self.assertEqual(first["fusions"]["status"],"conflitos_em_quarentena")
            self.assertEqual(first["fusions"]["unambiguousPairs"],5549)
            self.assertEqual(first["fusions"]["conflictingPairs"],3)
            self.assertFalse(first["fusions"]["mayActivate"])
            self.assertEqual(second["fusions"]["status"],"conflitos_em_quarentena")
            probe.assert_called_once()
            importer.assert_not_called()
            saved=home/"investigacoes"/(sha+".fusoes.json")
            self.assertTrue(saved.exists())
            self.assertEqual(json.loads(saved.read_text())["rom_sha256"],sha)
            self.assertFalse(catalog.profile_for(catalog.list()[0])[
                "supported_features"]["fusions"])

    def test_cache_report_bounded_and_ai_disabled_is_safe(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            image = home / "my-mod.iso"
            image.write_bytes(b"placeholder")
            sha = "a" * 64
            profile_path = home / "profiles" / "demo" / "profile.json"
            atomic_json(profile_path, {
                "name": "Mod teste", "rom_sha256": sha,
                "supported_features": {"cards": False, "effects": False},
                "verified": {"cartas": "pendente"},
            })
            cat = ModCatalog(home)
            atomic_json(cat.registry_file, {
                "schema": 1, "entries": [
                    {"source_path": str(image.resolve()), "file_name": image.name,
                     "sha256": sha, "profile_path": str(profile_path),
                     "level": "desconhecido"},
                ],
            })
            engine = MultiModIntelligence(cat)
            evidence = {"file": image.name, "hash_rom": sha, "features": {},
                        "candidates": {"fusion_tables_u16": []},
                        "uncertainties": [{"field": "fusoes", "status": "pendente"}],
                        "evidence": []}
            with patch("dueltrace_intelligence.investigate", return_value=evidence) as investigate:
                first = engine.inspect(image, use_ollama=False)
                second = engine.inspect(image, use_ollama=False)
                investigate.assert_called_once()
            self.assertEqual(first["state"], "analisado")
            self.assertEqual(second["state"], "cache")
            self.assertEqual(first["ai"], "desativada")
            report = json.loads(Path(first["report_path"]).read_text("utf-8"))
            self.assertEqual(report["hash_rom"], sha)
            self.assertFalse((home / "investigacoes" / (sha + ".ollama.json")).exists())


if __name__ == "__main__":
    unittest.main()
