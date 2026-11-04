"""Diagnóstico local para ISOs de mods com tabelas deslocadas/desconhecidas."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))

from auto_mods import ModCatalog, atomic_json
from dueltrace_mod_diagnostic import diagnose_layout
from dueltrace_web_bridge import DueltraceWebBridge
from dueltrace_web_security import ProtectedDesktopApi
from ia_local import minimal_evidence

SHA="d"*64


class UnknownISOTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name)
        self.scan=self.home/"analises"/"gog-mod"
        self.scan.mkdir(parents=True)
        self.report={
            "status":"incerto: estrutura não reconhecida; sem atribuições automáticas",
            "tipo_setor":2352,
            "nomes_status":"Codificação diferente/ambígua: 2/39 nomes, 31/722 cartas plausíveis",
            "drops_status":"Drops não validados: formato desconhecido",
            "arquivos_discos":[
                {"nome":"DATA/SCUS_123.45","lba":22,"tamanho":2010000},
                {"nome":"DATA/WA_MRG.MRG","lba":450,"tamanho":35000000},
            ],
            "executavel":"DATA/SCUS_123.45",
            "hash_executavel":"e"*64,
            "wa_total_bytes":35000000,
        }
        self.profile={
            "rom_sha256":SHA,
            "scan_result_dir":str(self.scan),
            "supported_features":{"cards":False,"drops":False,"art":False},
            "verified":{"cartas":"pendente","tabelas_drops":"pendente"},
        }

    def test_zero_counts_are_not_accepted_as_empty_image(self):
        result=diagnose_layout(self.report,self.profile)
        self.assertFalse(result["automaticExtractionComplete"])
        self.assertEqual(result["state"],"estrutura_desconhecida")
        self.assertEqual(result["indexedFiles"],2)
        self.assertEqual(result["sectorBytes"],2352)
        self.assertIn("DATA/SCUS_123.45",result["executableCandidates"])
        self.assertIn("DATA/WA_MRG.MRG",result["waCandidates"])
        self.assertTrue(any("Codificação diferente" in t for t in result["issues"]))
        self.assertTrue(any("Drops" in t for t in result["issues"]))
        self.assertNotIn(str(self.home),str(result))

    def test_missing_wa_gives_explicit_next_step(self):
        self.report["arquivos_discos"]=[
            {"nome":"DATA/SLUS_014.11","lba":22,"tamanho":2000000},
            {"nome":"DATA/OTHER.MRG","lba":450,"tamanho":40000000},
        ]
        info=diagnose_layout(self.report,self.profile)
        self.assertTrue(any("WA_MRG" in x for x in info["issues"]))
        self.assertIn("DATA/OTHER.MRG",info["waCandidates"])
        self.assertFalse(info["automaticExtractionComplete"])

    def test_ollama_receives_only_metadata_not_binary(self):
        info=diagnose_layout(self.report,self.profile)
        evidence=minimal_evidence({
            "scan_diagnostic":info,"file":"GOG-MOD.iso",
            "features":{},"inventory":{},"candidates":{},
        })
        self.assertIn("scan_diagnostic",evidence)
        self.assertEqual(evidence["scan_diagnostic"]["sectorBytes"],2352)
        self.assertEqual(len(evidence["scan_diagnostic"]["issues"]),2)
        self.assertNotIn("raw_bytes",str(evidence))
        self.assertNotIn(str(self.home),str(evidence))

    def test_token_protected_diagnosis_and_no_ai_without_click(self):
        atomic_json(self.scan/"relatorio.json",self.report)
        profile=self.home/"profiles"/SHA[:16]/"profile.json"
        atomic_json(profile,self.profile)
        source=self.home/"gog-mod.iso"
        source.write_bytes(b"test - not a game image")
        catalog=ModCatalog(self.home)
        atomic_json(catalog.registry_file,{"schema":1,"entries":[{
            "sha256":SHA,"file_name":source.name,
            "source_path":str(source),"profile_path":str(profile),
        }]})
        api=ProtectedDesktopApi(DueltraceWebBridge(catalog),"t"*64)
        with self.assertRaises(PermissionError):
            api.get_mod_scan_diagnostic("wrong",SHA)
        with patch("dueltrace_web_bridge.MultiModIntelligence.inspect") as ai:
            result=api.get_mod_scan_diagnostic("t"*64,SHA)
            self.assertFalse(result["automaticExtractionComplete"])
            self.assertEqual(result["ai"]["state"],"nao_solicitada")
            ai.assert_not_called()
            ai.return_value={"ai":"ollama_indisponivel",
                             "ai_message":"Modelo não encontrado."}
            result=api.get_mod_scan_diagnostic("t"*64,SHA,True)
            self.assertEqual(result["ai"]["state"],"ollama_indisponivel")
            ai.assert_called_once()
        with self.assertRaises(ValueError):
            api.get_mod_scan_diagnostic("t"*64,"../other",True)

    def test_scan_report_error_is_visible(self):
        info=diagnose_layout({
            "status":"erro/estrutura incompatível",
            "problema":"CD-ROM 2352 sem ISO9660 detectado",
        },self.profile)
        self.assertTrue(any("CD-ROM" in x for x in info["issues"]))
        self.assertTrue(any("ISO9660" in x for x in info["nextSteps"]))


if __name__=="__main__":
    unittest.main()
