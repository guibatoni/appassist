"""Regressões de engenharia reversa de tipos por ISO (sem ROM comercial)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scanner"))

from dueltrace_type_forensics import analyze_iso_types, apply_iso_type_evidence
from card_catalog import enrich_cards
from dueltrace_classic_cards import card_fields

ISO_A = "a" * 64
ISO_B = "b" * 64


def original_cards():
    return [
        {"id": i, "tipo": 0, "nivel": 4, "atk": 1200, "def": 800}
        for i in range(1, 723)
    ]


class AutomaticTypeForensicTests(unittest.TestCase):
    def test_original_type_kept_and_no_fake_validation(self):
        report = analyze_iso_types(original_cards(), rom_sha256=ISO_A)
        self.assertEqual(report["analyzed"], 722)
        self.assertEqual(report["unresolvedCodes"], [])
        self.assertEqual(report["status"], "codigos_compativeis_com_fm_nao_confirmados_em_jogo")
        self.assertFalse(report["mappingVerified"])
        self.assertFalse(report["inGameVerified"])
        self.assertEqual(report["counts"]["0"], 722)

    def test_extended_5bit_type_detected_from_iso_records(self):
        rows = original_cards()
        rows[0].update(tipo=24, nivel=9, atk=3900, def=3300)
        rows[1].update(tipo=24, nivel=10, atk=4000, def=4000)
        report = analyze_iso_types(rows, rom_sha256=ISO_A)
        self.assertEqual(report["unresolvedCodes"], [24])
        self.assertEqual(report["monsterLikeCodes"], [24])
        catalog = enrich_cards([
            {"id": c["id"], "type_id": c["tipo"], "level": c["nivel"],
             "atk": c["atk"], "def": c["def"]}
            for c in rows])
        enriched = apply_iso_type_evidence(catalog, report, rom_sha256=ISO_A)
        self.assertEqual(enriched[0]["category"], "Monstros")
        self.assertEqual(enriched[0]["type_label"], "Tipo #24 (a verificar)")
        self.assertEqual(card_fields(enriched[0])["kind"], "Tipo #24 (a verificar)")
        self.assertEqual(card_fields(enriched[0])["atk"], 3900)
        self.assertEqual(card_fields(enriched[2])["kind"], "Dragão")

    def test_fm_special_type_remapped_to_monster(self):
        rows = original_cards()
        for i in range(5):
            rows[i].update(tipo=20, nivel=6, atk=2000, def=1200)
        report = analyze_iso_types(rows, rom_sha256=ISO_A)
        self.assertEqual(report["unresolvedCodes"], [20])
        self.assertEqual(report["suspectedRemaps"], [20])
        self.assertIn(20, report["monsterLikeCodes"])

    def test_isolated_special_anomaly_does_not_hide_normal_spells(self):
        rows = original_cards()
        for i in range(10):
            rows[i].update(tipo=20, nivel=0, atk=0, def=0)
        rows[0].update(nivel=8, atk=2800, def=2400)
        report = analyze_iso_types(rows, rom_sha256=ISO_A)
        self.assertNotIn(20, report["unresolvedCodes"])
        self.assertIn(1, report["isolatedCardIds"])
        catalog = enrich_cards([
            {"id": c["id"], "type_id": c["tipo"], "level": c["nivel"],
             "atk": c["atk"], "def": c["def"]}
            for c in rows])
        updated = apply_iso_type_evidence(catalog, report, rom_sha256=ISO_A)
        self.assertEqual(updated[0]["type_label"], "Tipo #20 (a verificar)")
        self.assertEqual(updated[1]["type_label"], "Magia")

    def test_type_codes_are_bound_to_the_active_iso_sha(self):
        rows = original_cards()
        rows[0]["tipo"] = 31
        report = analyze_iso_types(rows, rom_sha256=ISO_A)
        catalog = enrich_cards([{"id": 1, "type_id": 31}])
        untouched = apply_iso_type_evidence(catalog, report, rom_sha256=ISO_B)
        self.assertNotIn("type_semantics_unresolved", untouched[0])
        self.assertNotEqual(untouched[0], apply_iso_type_evidence(catalog, report, rom_sha256=ISO_A)[0])

    def test_never_invents_a_label_for_unknown_type(self):
        rows = original_cards()
        rows[0].update(tipo=31, atk=0, def=0, nivel=0)
        report = analyze_iso_types(rows, rom_sha256=ISO_A)
        catalog = [{"id": 1, "type_id": 31, "category": "Não identificado",
                    "type_label": "Código 31"}]
        unknown = apply_iso_type_evidence(catalog, report, rom_sha256=ISO_A)
        self.assertEqual(unknown[0]["category"], "Não identificado")
        self.assertEqual(unknown[0]["type_label"], "Tipo #31 (a verificar)")
        self.assertIsNone(card_fields(unknown[0])["atk"])

    def test_incomplete_or_invalid_layout_cannot_be_promoted(self):
        rows = original_cards()
        cases = [rows[:721], [{**c} for c in rows]]
        cases[1][10]["id"] = 5
        for bad in cases:
            report = analyze_iso_types(bad, rom_sha256=ISO_A)
            self.assertEqual(report["analyzed"], 0)
            self.assertFalse(report["mappingVerified"])
        with self.assertRaises(ValueError):
            analyze_iso_types(rows, rom_sha256="../wrong")

    def test_scanner_profile_and_renderer_use_iso_evidence(self):
        scanner = (ROOT / "scanner/scanner_multiiso.py").read_text("utf-8")
        importer = (ROOT / "scanner/importador_perfis.py").read_text("utf-8")
        assets = (ROOT / "scanner/fm_deep_assets.py").read_text("utf-8")
        renderer = (ROOT / "scanner/dueltrace_classic_cards.py").read_text("utf-8")
        self.assertIn("analyze_iso_types(", scanner)
        self.assertIn('"type_analysis"', scanner)
        self.assertIn('"tipos_iso.json"', scanner)
        self.assertIn("type_analysis=info.get", scanner)
        self.assertIn("apply_iso_type_evidence(", importer)
        self.assertIn('"type_analysis": type_analysis', importer)
        self.assertIn("unresolved_types", assets)
        self.assertIn("type_analysis=type_analysis", assets)
        self.assertIn("apply_iso_type_evidence(", renderer)


if __name__ == "__main__":
    unittest.main()
