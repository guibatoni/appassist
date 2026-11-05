"""Relatórios de compatibilidade sem vazar ROM, RAM, caminhos ou falso RANK."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))
from auto_mods import ModCatalog, atomic_json
from dueltrace_compatibility_matrix import (
    build_compatibility_matrix,MAX_MODS,main)


class CompatibilityMatrixTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.catalog=ModCatalog(self.root/"home")
        self.sha="c"*64
        self.profile={
            "rom_sha256":self.sha,
            "verified":{"cartas":"pendente","oponentes":"pendente"},
            "supported_features":{"cards":False,"opponents":False,
                                  "drops":False,"fusions":False,
                                  "ranks":False},
        }
        scan=self.catalog.home/"analises"/"fixture1"
        scan.mkdir(parents=True)
        self.profile["scan_result_dir"]=str(scan)
        report={
            "status":"incerto: estrutura não reconhecida",
            "relocated_name_layouts":{
                "state":"layout_candidato_localizado",
                "candidates":[{"pointerBase":1234,"validated":False}]},
            "card_attribute_layouts":{
                "state":"hipoteses_ambiguas",
                "links":[{"packedBase":4567},{"packedBase":7890}]},
            "wa_resource_selection":{
                "state":"recurso_candidato_estrutural",
                "candidates":[{"name":"PRIVATE SECRET PATH"}]},
            "drop_layout_discovery":{
                "state":"layout_candidato_unico",
                "candidates":[{"opponentBase":4567}]},
            "rank_analysis":{"status":"layout_unknown"}}
        (scan/"relatorio.json").write_text(
            json.dumps(report,ensure_ascii=False),encoding="utf-8")
        path=self.catalog.home/"profiles"/self.sha[:16]/"profile.json"
        atomic_json(path,self.profile)
        entry={"sha256":self.sha,"profile_path":str(path),
               "level":"desconhecido","source_path":"C:/SECRET/MOD.iso"}
        atomic_json(self.catalog.registry_file,{"schema":1,"entries":[entry]})

    def test_report_reuses_only_same_sha_and_limited_evidence(self):
        report=build_compatibility_matrix(self.catalog)
        self.assertEqual(report["modCount"],1)
        row=report["mods"][0]
        self.assertEqual(row["sha256"],self.sha)
        self.assertEqual(row["modeAvailable"],"basic")
        self.assertFalse(row["features"]["cards"])
        self.assertFalse(row["inGameVerified"])
        self.assertEqual(row["discovery"]["names"],
                         "layout_candidato_localizado")
        self.assertEqual(row["candidates"]["attributeLayouts"],2)
        self.assertEqual(row["candidates"]["dropLayouts"],1)
        raw=json.dumps(report)
        self.assertNotIn("PRIVATE SECRET PATH",raw)
        self.assertNotIn("C:/SECRET",raw)
        self.assertNotIn("pointerBase",raw)
        self.assertNotIn("packedBase",raw)
        self.assertFalse(report["inGameValidationClaimed"])

    def test_invalid_or_mismatching_sha_is_not_reported(self):
        path=Path(self.profile["scan_result_dir"])
        bad=dict(self.profile,rom_sha256="a"*64)
        atomic_json(self.catalog.home/"profiles"/self.sha[:16]/"profile.json",bad)
        result=build_compatibility_matrix(self.catalog)
        self.assertEqual(result["modCount"],0)
        self.assertEqual(result["featureCoverage"]["cards"],0)

    def test_report_from_outside_home_is_not_read(self):
        p=dict(self.profile,scan_result_dir=str(self.root))
        path=self.catalog.home/"profiles"/self.sha[:16]/"profile.json"
        atomic_json(path,p)
        report=build_compatibility_matrix(self.catalog)
        self.assertEqual(report["mods"][0]["discovery"]["names"],
                         "nao_analisado")

    def test_corrupted_scan_image_is_not_marked_basic(self):
        p=dict(self.profile,scanner_error="invalid ISO9660")
        path=self.catalog.home/"profiles"/self.sha[:16]/"profile.json"
        atomic_json(path,p)
        out=build_compatibility_matrix(self.catalog)
        self.assertEqual(out["mods"][0]["modeAvailable"],"scan_error")
        self.assertFalse(out["mods"][0]["features"]["ranks"])

    def test_cli_exports_compact_report_to_user_selected_location(self):
        output=self.root/"private"/"matrix.json"
        self.assertEqual(main(["--home",str(self.catalog.home),
                               "--output",str(output)]),0)
        data=json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(data["modCount"],1)
        self.assertEqual(data["mods"][0]["sha256"],self.sha)
        self.assertFalse(data["inGameValidationClaimed"])


if __name__=="__main__":
    unittest.main()
