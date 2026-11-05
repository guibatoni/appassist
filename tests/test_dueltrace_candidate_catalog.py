"""Reconstrução de catálogo estrutural sem publicação aos jogadores."""
from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))

from dueltrace_candidate_catalog import build_quarantined_catalog
from dueltrace_card_attribute_probe import discover_card_attribute_layout
from test_dueltrace_card_attribute_probe import (
    make_exe,NAME_LAYOUT,SLUS_ATTRIBUTES,DETAIL_BASE
)
from scanner_multiiso import SCAN_PARSER_REVISION

SHA="a"*64


def hypothesis(exe):
    return discover_card_attribute_layout(
        exe,name_layouts=[NAME_LAYOUT],
        packed_base=SLUS_ATTRIBUTES,detail_base=DETAIL_BASE)


class QuarantinedCatalogTests(unittest.TestCase):
    def test_reconstructs_722_names_stats_and_39_opponents_same_exe(self):
        exe=make_exe()
        proposal=hypothesis(exe)
        self.assertEqual(proposal["state"],"candidatos_vinculados")
        result=build_quarantined_catalog(exe,SHA,proposal)
        self.assertEqual(result["status"],"catalogo_candidato_reconstruido")
        self.assertEqual(result["romSha256"],SHA)
        self.assertEqual(result["exeSha256"],hashlib.sha256(exe).hexdigest())
        self.assertEqual(result["cardsCount"],722)
        self.assertEqual(result["opponentsCount"],39)
        self.assertEqual(result["cards"][0]["id"],1)
        self.assertEqual(result["cards"][0]["nome"],"CARD0001")
        self.assertEqual(result["cards"][0]["atk"],850)
        self.assertEqual(result["opponents"][-1]["nome"],"OPP39")
        self.assertEqual(result["fieldEncoding"],"fm_packed_722_v1")
        self.assertFalse(result["validated"])
        self.assertFalse(result["inGameVerified"])
        self.assertFalse(result["mayActivate"])

    def test_rejects_exe_mismatch_to_prevent_cross_mod_data(self):
        exe=make_exe()
        report=hypothesis(exe)
        different=exe+b"additional unrelated bytes"
        out=build_quarantined_catalog(different,SHA,report)
        self.assertEqual(out["status"],"assinatura_executavel_divergente")
        self.assertEqual(out["cards"],[])
        self.assertEqual(out["opponents"],[])

    def test_multiple_layouts_never_generate_catalog(self):
        exe=make_exe()
        report=hypothesis(exe)
        report["state"]="hipoteses_ambiguas"
        report["links"]=report["links"]*2
        out=build_quarantined_catalog(exe,SHA,report)
        self.assertEqual(out["status"],"layout_nao_unico")
        self.assertEqual(out["cardsCount"],0)

    def test_invalid_sha_never_creates_candidate(self):
        exe=make_exe()
        out=build_quarantined_catalog(exe,"not-valid",hypothesis(exe))
        self.assertEqual(out["status"],"entrada_invalida")
        self.assertEqual(out["cards"],[])

    def test_catalog_file_is_not_regular_cards_csv_or_runtime_profile(self):
        source=(ROOT/"scanner/scanner_multiiso.py").read_text(encoding="utf-8")
        self.assertIn("build_quarantined_catalog(",source)
        self.assertIn("catalogo_candidato_nao_verificado.json",source)
        self.assertIn("candidate_catalogue",source)
        self.assertIn("SCAN_PARSER_REVISION=17",source)
        self.assertGreaterEqual(SCAN_PARSER_REVISION,16)
        self.assertNotIn("cards=candidate_catalog",source)
        self.assertNotIn("opponents=candidate_catalog",source)


if __name__=="__main__":
    unittest.main()
