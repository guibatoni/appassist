"""Cross-ISO evidence regression: no ROM upload and no false feature promotion."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scanner"))
from dueltrace_iso_differential import (
    fingerprint_scan, compare_structures, _load, MAX_COMPARISONS,
)


def report(char: str, *, cards=722, opponents=39, matrices=117, structural=False):
    return {
        "sha256": char * 64,
        "scan_parser_revision": 29,
        "arquivo": "DO-NOT-PUBLISH-" + char + ".iso",
        "resultado_dir": "C:/PRIVATE/USER/DATA",
        "cartas": cards, "oponentes": opponents, "tabelas_drops": matrices,
        "tipo_setor": 2352,
        "boot_alvo_indexado": True,
        "opponent_identification": (
            "extraidos_estruturalmente" if structural else "verificado"),
        "wa_resource_selection": {
            "state": "recurso_candidato_estrutural",
            "limitReached": False,
            "selected_bytes": "SECRET",
            "source": "G0SD/private.bin",
        },
        "rotulos_ranks_confirmados": False,
        "drop_group_mapping_status": "grupos_nao_identificados",
        "layout_discovery": {
            "executables": [{
                "name": "PRIVATE.EXE",
                "executableHeader": {"headerCoherent": True},
            }],
            "resources": [{"name":"SECRET.MRG"}],
        },
        "fusion_recipes": [{"a":1,"b":2,"result":3}],
        "artes": [{"content":"PRIVATE"}],
    }


class StructuralDifferentialTests(unittest.TestCase):
    def test_positive_custom_mod_baseline_remains_distinct_from_gog(self):
        good = report("a", structural=False)
        gog = report("b", structural=True)
        fingerprint = fingerprint_scan(good)
        self.assertEqual(fingerprint["cards"]["state"], "complete_722")
        self.assertEqual(fingerprint["opponents"]["state"],
                         "names_extracted_id_unverified")
        self.assertEqual(fingerprint["drops"]["matrixCount"], 117)
        self.assertFalse(fingerprint["drops"]["opponentToBlockVerified"])
        self.assertFalse(fingerprint["fusion"]["recipesVerified"])
        comparison = compare_structures(good, [gog])
        self.assertIn("opponents",
            [item["stage"] for item in comparison["compared"][0]["differences"]])
        self.assertFalse(comparison["automaticallyActivatesFeatures"])
        self.assertFalse(comparison["compared"][0]["inGameValidated"])

    def test_no_paths_bytes_names_or_recipes_exported(self):
        good = report("a")
        rendered = json.dumps(fingerprint_scan(good))
        compared = json.dumps(compare_structures(good, [good]))
        for forbidden in ("C:/PRIVATE", "DO-NOT-PUBLISH", "SECRET",
                          "PRIVATE.EXE", "fusion_recipes", "selected_bytes",
                          "G0SD/private.bin"):
            self.assertNotIn(forbidden, rendered)
            self.assertNotIn(forbidden, compared)

    def test_unknown_mod_never_becomes_validated(self):
        unknown = report("c", cards=0, opponents=0, matrices=0)
        unknown["wa_resource_selection"]["state"] = "candidatos_excedem_limite"
        unknown["wa_resource_selection"]["limitReached"] = True
        fingerprint = fingerprint_scan(unknown)
        self.assertEqual(fingerprint["cards"]["state"], "not_extracted")
        self.assertEqual(fingerprint["opponents"]["state"], "not_extracted")
        self.assertEqual(fingerprint["resources"]["state"], "candidatos_excedem_limite")
        self.assertTrue(fingerprint["resourceLimitReached"])
        self.assertEqual(fingerprint["fusion"]["state"], "not_assessed_by_multiiso_scan")
        self.assertFalse(fingerprint["opponents"]["inGameIdentityVerified"])

    def test_reject_invalid_local_report_and_large_batch(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "good.json"
            p.write_text(json.dumps(report("a")), encoding="utf-8")
            self.assertEqual(_load(p)["sha256"], "a"*64)
            p.write_text('{"sha256":"not-full-sha"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                _load(p)
        with self.assertRaises(ValueError):
            compare_structures(report("a"), [report("b")] * (MAX_COMPARISONS+1))

    def test_missing_data_does_not_generate_identity(self):
        fp = fingerprint_scan({})
        self.assertIsNone(fp["romFingerprint"])
        self.assertEqual(fp["cards"]["count"], 0)
        self.assertFalse(fp["opponents"]["inGameIdentityVerified"])
        self.assertEqual(fp["fusion"]["state"], "not_assessed_by_multiiso_scan")
        self.assertFalse(fp["drops"]["rankGroupsVerified"])


if __name__=="__main__":
    unittest.main()
