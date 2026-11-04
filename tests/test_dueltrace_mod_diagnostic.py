"""Diagnóstico local para ISOs de mods com tabelas deslocadas/desconhecidas."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))

from auto_mods import ModCatalog, atomic_json
from dueltrace_mod_diagnostic import diagnose_layout
from scanner_multiiso import select_known_executable_layout, inspect_system_cnf, inspect_file_signatures
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

    def test_alternative_executable_can_recover_known_card_layout(self):
        class FakeDisc:
            files={
                "DATA/SLUS_014.11":(10,2000000),
                "DATA/SCUS_123.45":(30,2100000),
            }
            def get(self,name):
                return name.encode("ascii")
        def decode(raw):
            if b"SCUS" in raw:
                return [{"id":1,"nome":"Jono"}],[{"id":1,"nome":"Flower Wolf"}],"39/39, 722/722"
            return [],[],"Codificação diferente: 0/39 e 0/722"
        candidates=["DATA/SLUS_014.11","DATA/SCUS_123.45"]
        with patch("scanner_multiiso.decode_names",side_effect=decode):
            chosen,data,opponents,cards,status,tried=(
                select_known_executable_layout(FakeDisc(),candidates))
        self.assertEqual(chosen,"DATA/SCUS_123.45")
        self.assertEqual(cards[0]["nome"],"Flower Wolf")
        self.assertEqual(len(tried),2)
        self.assertFalse(tried[0]["recognized"])
        self.assertTrue(tried[1]["recognized"])

    def test_alternative_unknown_executable_cannot_be_approved(self):
        class FakeDisc:
            files={"A":(1,2000000),"B":(2,2100000)}
            def get(self,name):
                return name.encode("ascii")
        with patch("scanner_multiiso.decode_names",
                   return_value=([],[],"Offsets incompatíveis")):
            chosen,data,opponents,cards,status,tried=(
                select_known_executable_layout(FakeDisc(),["A","B"]))
        self.assertEqual(chosen,"A")
        self.assertEqual(opponents,[])
        self.assertEqual(cards,[])
        self.assertEqual(len(tried),2)

    def test_nine_file_unknown_iso_lists_every_file_and_boot_clue(self):
        files=[
            {"nome":"SYSTEM.CNF","lba":22,"tamanho":70},
            {"nome":"DATA.PAK","lba":50,"tamanho":234567890},
            {"nome":"GAME.DAT","lba":70000,"tamanho":12000000},
        ]+[
            {"nome":f"CUSTOM_{i}.BIN","lba":i*100,"tamanho":i*1000}
            for i in range(6)]
        self.report["arquivos_discos"]=files
        self.report["system_cnf"]={
            "found":True,"boot_target":"CUSTOM_1.BIN",
            "status":"BOOT identificado, apenas como indicação de arquivo",
        }
        result=diagnose_layout(self.report,self.profile)
        self.assertEqual(result["indexedFiles"],9)
        self.assertEqual(len(result["files"]),9)
        self.assertEqual(result["files"][1]["name"],"DATA.PAK")
        self.assertEqual(result["files"][1]["size"],234567890)
        self.assertEqual(result["possibleResourceFiles"][0]["name"],"DATA.PAK")
        self.assertEqual(result["possibleResourceFiles"][0]["size"],234567890)
        self.assertTrue(all(row["name"]!="CUSTOM_1.BIN"
                            for row in result["possibleResourceFiles"]))
        self.assertEqual(result["systemCnf"]["bootTarget"],"CUSTOM_1.BIN")
        self.assertTrue(result["systemCnf"]["bootTargetIndexed"])
        self.assertFalse(result["automaticExtractionComplete"])

    def test_bounded_system_cnf_disc_boot_uses_unknown_name_as_clue(self):
        class FakeDisc:
            files={"SYSTEM.CNF":(12,55),"CUSTOM.EXE2":(13,1024)}
            def get(self,name,limit_bytes=None):
                self.last=(name,limit_bytes)
                return b"BOOT = cdrom:\\CUSTOM.EXE2;1\r\nTCB=4"
        disk=FakeDisc()
        status=inspect_system_cnf(disk)
        self.assertTrue(status["found"])
        self.assertEqual(status["boot_target"],"CUSTOM.EXE2")
        self.assertEqual(disk.last,("SYSTEM.CNF",16384))

    def test_system_cnf_absence_is_not_invented(self):
        class FakeDisc:
            files={"DATA.PAK":(1,2048)}
        result=inspect_system_cnf(FakeDisc())
        self.assertFalse(result["found"])
        self.assertIsNone(result["boot_target"])

    def test_invalid_boot_parent_path_is_rejected(self):
        class FakeDisc:
            files={"SYSTEM.CNF":(1,55)}
            def get(self,name,limit_bytes=None):
                return b"BOOT = cdrom:\\..\\MALWARE.EXE;1\r\n"
        info=inspect_system_cnf(FakeDisc())
        self.assertIsNone(info["boot_target"])

    def test_nonstandard_gog_boot_missing_from_index_not_called_empty_game(self):
        self.report["system_cnf"]={
            "found":True,"boot_target":"GOG_VNT.223",
            "status":"BOOT identificado, apenas como indicação de arquivo",
        }
        diagnosis=diagnose_layout(self.report,self.profile)
        self.assertFalse(diagnosis["automaticExtractionComplete"])
        self.assertEqual(diagnosis["systemCnf"]["bootTarget"],"GOG_VNT.223")
        self.assertFalse(diagnosis["systemCnf"]["bootTargetIndexed"])
        self.assertTrue(any("GOG_VNT.223" in x for x in diagnosis["issues"]))
        self.assertTrue(any("outra trilha" in x for x in diagnosis["nextSteps"]))
        self.assertFalse(diagnosis["cardsVerified"])

    def test_nonstandard_indexed_boot_with_psx_signature_still_not_verified(self):
        self.report["system_cnf"]={
            "found":True,"boot_target":"GOG_VNT.223","status":"BOOT identificado"}
        self.report["arquivos_discos"].append({
            "nome":"GOG_VNT.223","lba":8000,"tamanho":2000000})
        self.report["assinaturas_arquivos"]=[
            {"nome":"GOG_VNT.223","assinatura":"psx_executavel",
             "prefix_sha256":"f"*16},
        ]
        diagnosis=diagnose_layout(self.report,self.profile)
        self.assertTrue(diagnosis["systemCnf"]["bootTargetIndexed"])
        self.assertEqual(diagnosis["systemCnf"]["bootFileSignature"],
                         "psx_executavel")
        self.assertIn("GOG_VNT.223",diagnosis["executableCandidates"])
        self.assertFalse(diagnosis["automaticExtractionComplete"])

    def test_bounded_signature_scan_does_not_read_large_binary(self):
        class FakeDisc:
            files={"GOG_VNT.223":(100,2500000),
                   "UNKNOWN.DAT":(300,100000000)}
            def __init__(self):self.calls=[]
            def get(self,name,limit_bytes=None):
                self.calls.append((name,limit_bytes))
                if name=="GOG_VNT.223":
                    return b"PS-X EXE" + bytes(24)
                return bytes(range(32))
        disc=FakeDisc()
        signatures=inspect_file_signatures(disc)
        self.assertEqual(len(signatures),2)
        self.assertEqual(signatures[0]["assinatura"],"psx_executavel")
        self.assertEqual(disc.calls,[("GOG_VNT.223",32),
                                     ("UNKNOWN.DAT",32)])
        self.assertEqual(len(signatures[0]["prefix_sha256"]),16)

    def test_cached_ollama_claims_about_empty_iso_are_suppressed(self):
        atomic_json(self.scan/"relatorio.json",self.report)
        profile_path=self.home/"profiles"/SHA[:16]/"profile.json"
        atomic_json(profile_path,self.profile)
        source=self.home/"gog-mod.iso"
        source.write_bytes(b"test not a game ISO")
        catalog=ModCatalog(self.home)
        atomic_json(catalog.registry_file,{"schema":1,"entries":[{
            "sha256":SHA,"file_name":source.name,"source_path":str(source),
            "profile_path":str(profile_path)}]})
        ai_file=self.home/"investigacoes"/"report.ollama.json"
        atomic_json(ai_file,{
            "resumo":"Foi verificado que a ISO não contém cartas, oponentes ou drops",
            "prioridades":["cartas","oponentes","tabelas_drops"],
        })
        api=ProtectedDesktopApi(DueltraceWebBridge(catalog),"t"*64)
        with patch("dueltrace_web_bridge.MultiModIntelligence.inspect",
                   return_value={"ai":"hipoteses_em_cache",
                                 "ai_report_path":str(ai_file)}):
            result=api.get_mod_scan_diagnostic("t"*64,SHA,True)
        self.assertEqual(result["ai"]["state"],"hipoteses_em_cache")
        self.assertTrue(result["ai"]["summarySuppressed"])
        self.assertIn("NÃO comprova ausência",result["ai"]["resumo"])
        self.assertNotIn("Foi verificado",result["ai"]["resumo"])
        self.assertFalse(result["automaticExtractionComplete"])

    def test_scan_report_error_is_visible(self):
        info=diagnose_layout({
            "status":"erro/estrutura incompatível",
            "problema":"CD-ROM 2352 sem ISO9660 detectado",
        },self.profile)
        self.assertTrue(any("CD-ROM" in x for x in info["issues"]))
        self.assertTrue(any("ISO9660" in x for x in info["nextSteps"]))


if __name__=="__main__":
    unittest.main()
