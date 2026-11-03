"""Regressões: diagnóstico por mod e cache de hipóteses do Ollama."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scanner"))

from auto_mods import ModCatalog, atomic_json
from dueltrace_diagnostics import art_diagnostic, mod_diagnostic, format_diagnostic
from dueltrace_intelligence import MultiModIntelligence, local_report_fingerprint


class PerModDiagnosticTests(unittest.TestCase):
    def test_art_states_do_not_conflate_missing_and_failed(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            profile = {"scan_result_dir": str(folder)}
            self.assertEqual(art_diagnostic(profile)["state"], "sem registro")
            atomic_json(folder / "relatorio.json", {"art_requested": False})
            self.assertEqual(art_diagnostic(profile)["state"], "não solicitada")
            atomic_json(folder / "relatorio.json", {
                "art_requested": True, "artes_extraidas": 0,
                "artes_obs": "Layout não reconhecido"
            })
            self.assertEqual(art_diagnostic(profile)["state"], "nenhuma arte extraída")
            atomic_json(folder / "relatorio.json", {
                "art_requested": True, "artes_extraidas": 34,
                "artes_obs": "Container truncado"
            })
            self.assertEqual(art_diagnostic(profile)["state"], "parcial")
            atomic_json(folder / "relatorio.json", {
                "art_requested": True, "artes_extraidas": 722,
                "artes_obs": "722 imagens exportadas"
            })
            self.assertEqual(art_diagnostic(profile)["state"], "extraída")

    def test_diagnostic_respects_verified_features_and_avoids_private_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            profile = {
                "scan_result_dir": str(Path(temp)),
                "supported_features": {"cards": True, "drops": True, "fusions": False},
                "cards": [{"id": 1, "name": "Teste", "effect_text": "Luz"},
                          {"id": 2, "effect_text": "Fogo", "effect_source": "ISO"}],
                "drops": [{"card_id": 1}],
                "fusion_recipes": [{"a": 1, "b": 2, "result": 3}],
                "verified": {"cartas": "verificado"},
            }
            entry = {"file_name": "teste.iso", "sha256": "f"*64,
                     "level": "parcial_revisar"}
            result = mod_diagnostic(entry,profile,intelligence={"ai":"hipoteses_em_cache"})
            self.assertEqual(result["effects"], 1)
            self.assertEqual(result["fusions_verified"], 0)
            self.assertEqual(result["drop_entries"], 1)
            text = format_diagnostic(result)
            self.assertIn("hipoteses_em_cache", text)
            self.assertIn("Artes:", text)
            self.assertNotIn(str(Path(temp)), text)

    def test_modified_profile_forces_cache_refresh(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            image=folder/"test.iso"
            image.write_bytes(b"sample")
            sha="a"*64
            profile_path=folder/"profiles"/sha[:12]/"profile.json"
            profile={"rom_sha256":sha,"name":"Mod teste",
                     "supported_features":{"cards":False},
                     "verified":{"cartas":"pendente"}}
            atomic_json(profile_path,profile)
            catalog=ModCatalog(folder)
            entry={"sha256":sha,"source_path":str(image.resolve()),
                   "file_name":image.name,"profile_path":str(profile_path),
                   "level":"desconhecido"}
            atomic_json(catalog.registry_file,{"schema":1,"entries":[entry]})
            report={"file":"test.iso","hash_rom":sha,"features":{},
                    "candidates":{"fusion_tables_u16":[]},"uncertainties":[],
                    "evidence":[]}
            with (
                patch("dueltrace_intelligence.investigate",
                      side_effect=lambda _image, p, **_kw: {**report, "features": dict(p["verified"])}) as inspect,
                patch("dueltrace_intelligence.ollama_status",
                      return_value={"available":True,"state":"pronto"}) as status,
                patch("dueltrace_intelligence.analyse_with_local_ai",
                      return_value={"status":"SOMENTE HIPÓTESES"}) as llm,
            ):
                engine=MultiModIntelligence(catalog)
                one=engine.inspect(image)
                two=engine.inspect(image)
                self.assertEqual(one["ai"],"hipoteses_salvas")
                self.assertEqual(two["ai"],"hipoteses_em_cache")
                self.assertEqual(inspect.call_count,1)
                self.assertEqual(llm.call_count,1)
                # Alterar metadados com crescimento do arquivo invalida o SHA das evidências.
                profile["verified"]["cartas"]="pendente_reavaliar"
                atomic_json(profile_path,profile)
                three=engine.inspect(image)
                self.assertEqual(three["state"],"analisado")
                self.assertEqual(three["ai"],"hipoteses_salvas")
                self.assertEqual(inspect.call_count,2)
                self.assertEqual(llm.call_count,2)


if __name__ == "__main__":
    unittest.main()
