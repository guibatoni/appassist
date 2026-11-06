"""Regression tests for local-only forensic evidence and optional Ollama."""
from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from urllib.error import URLError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))
sys.path.insert(0,str(ROOT/"tests"))

from scanner_multiiso import SLUS_PTR_BASE, SLUS_TEXT_BASE
from dueltrace_independent_opponents import (
    compact_opponent_evidence, explain_opponent_blocker)
from dueltrace_forensic_ai import numeric_evidence, review_with_ollama, ENDPOINT
from test_dueltrace_independent_opponents import relocated_opponents, probe


class ForensicReviewTests(unittest.TestCase):
    def test_alt_marker_records_are_counted_not_shared(self):
        scan=probe(relocated_opponents(terminator=0xfe))
        report=compact_opponent_evidence(scan)
        deep=report["forensicEvidence"]
        self.assertEqual(deep["status"],"janelas_auditadas")
        self.assertGreaterEqual(len(deep["windows"]),1)
        main=deep["windows"][0]
        self.assertEqual(main["candidateReadable"],39)
        self.assertEqual(main["pointerCountDistinct"],39)
        self.assertEqual(main["pointerNonIncreasingPairs"],0)
        self.assertEqual(main["boundaryDecision"],"delimitador_fisico_coerente")
        self.assertNotIn("OPP01",json.dumps(report))
        self.assertNotIn("quarantinedRecords",report)
        self.assertFalse(deep["mayPromote"])

    def test_nonzero_payload_receives_specific_diagnostic(self):
        exe=bytearray(relocated_opponents(terminator=0xfe))
        ptr=struct.unpack_from("<H",exe,SLUS_PTR_BASE+0x360*2)[0]
        pos=SLUS_TEXT_BASE+ptr
        marker=exe.index(0xfe,pos,pos+32)
        exe[marker+1]=7
        report=probe(bytes(exe))
        self.assertIsNone(report["selected"])
        compact=compact_opponent_evidence(report)
        self.assertEqual(compact["reasonCode"],"fronteira_dados_apos_marcador")
        self.assertEqual(compact["forensicEvidence"]["windows"][0]["boundaryDecision"],
                         "dados_apos_marcador")
        self.assertFalse(compact["validated"])
        self.assertFalse(compact["dropsVerified"])

    def test_mixed_markers_are_rejected_without_publishing_names(self):
        exe=bytearray(relocated_opponents(terminator=0xfe))
        ptr=struct.unpack_from("<H",exe,SLUS_PTR_BASE+0x360*2)[0]
        pos=SLUS_TEXT_BASE+ptr
        marker=exe.index(0xfe,pos,pos+32)
        exe[marker]=0xfd
        result=probe(bytes(exe))
        self.assertIsNone(result["selected"])
        deep=compact_opponent_evidence(result)["forensicEvidence"]
        self.assertEqual(deep["windows"][0]["boundaryDecision"],
                         "marcadores_inconsistentes")

    def test_serialized_evidence_does_not_expose_names_or_full_hash(self):
        report=probe(relocated_opponents(terminator=0xfe))
        compact=compact_opponent_evidence(report)
        serialized=json.dumps(compact)
        self.assertNotIn("OPP",serialized)
        self.assertNotIn(report["romSha256"],serialized)
        self.assertNotIn("quarantinedRecords",serialized)

    def test_prompt_cannot_include_file_paths_names_hashes_or_raw_text(self):
        scan=probe(relocated_opponents(terminator=0xfe))
        report={
            "file":"PRIVATE-C:\\Secret\\mod.iso",
            "romSha256":"superprivate",
            "independent_opponent_discovery":{
                "forensicEvidence":scan["forensicEvidence"],
                "candidateNames":["SECRET-OPPONENT-DO-NOT-SEND"],
                "path":"PRIVATE-C:\\Secret\\mod.iso",
            }
        }
        captured=[]
        def opener(req,timeout):
            self.assertEqual(req.full_url,ENDPOINT)
            body=req.data.decode("utf8")
            captured.append(body)
            return BytesIO(json.dumps({
                "response":json.dumps({"causa":"delimitador_fisico_coerente",
                                       "acoes":["buscar_referencias_mips"]})}).encode())
        answer=review_with_ollama(report,opener=opener)
        self.assertEqual(answer["status"],"hipotese_local_sem_validacao")
        self.assertEqual(answer["actions"],["buscar_referencias_mips"])
        for forbidden in ("PRIVATE-C:", "SECRET-OPPONENT", "romSha256","superprivate"):
            self.assertNotIn(forbidden,captured[0])
        self.assertFalse(answer["mayActivate"])
        self.assertFalse(answer["inGameVerified"])

    def test_no_ollama_and_bad_input_fail_closed(self):
        report={"independent_opponent_discovery":{
            "forensicEvidence":probe(relocated_opponents())["forensicEvidence"]}}
        def offline(req,timeout):
            raise URLError("service not installed")
        self.assertEqual(review_with_ollama(report,opener=offline)["status"],
                         "ollama_indisponivel_ou_resposta_invalida")
        self.assertEqual(review_with_ollama({})["status"],
                         "sem_evidencia_estrutural")
        self.assertEqual(review_with_ollama(report,model="evil\nmodel")["status"],
                         "modelo_invalido")

    def test_untrusted_model_cannot_make_up_new_drops(self):
        report={"independent_opponent_discovery":{
            "forensicEvidence":probe(relocated_opponents())["forensicEvidence"]}}
        def opener(req,timeout):
            return BytesIO(json.dumps({"response":json.dumps({
                "causa":"fusão confirmada", "acoes":["habilitar_drops", "inspecionar_ponteiros"]
            })}).encode())
        response=review_with_ollama(report,opener=opener)
        self.assertEqual(response["status"],"resposta_nao_confiavel")
        self.assertFalse(response["dropsVerified"])
        self.assertFalse(response["ranksVerified"])

    def test_untrusted_model_actions_are_filtered(self):
        report={"independent_opponent_discovery":{
            "forensicEvidence":probe(relocated_opponents())["forensicEvidence"]}}
        def opener(req,timeout):
            return BytesIO(json.dumps({"response":json.dumps({
                "causa":"incompleto","acoes":["habilitar_drops","inspecionar_ponteiros"]
            })}).encode())
        ans=review_with_ollama(report,opener=opener)
        self.assertEqual(ans["actions"],["inspecionar_ponteiros"])
        self.assertFalse(ans["mayActivate"])

    def test_nontextual_diagnostic_keys_are_bounded(self):
        report={"independent_opponent_discovery":{"forensicEvidence":{"windows":[{
            "boundaryDecision":["install malware"],
            "statusHistogram":{"C:\\Secret":10,"ff_encontrado":99},
            "firstInvalidByteHistogram":{"0xFE":39,"PRIVATE":39},
            "pointerSpanMax":1_000_000_000,
            "candidateReadable":39,
        }]}}}
        data=numeric_evidence(report)
        row=data["windows"][0]
        self.assertEqual(row["boundaryDecision"],"incompleto")
        self.assertEqual(row["statusHistogram"],{})
        self.assertEqual(row["firstInvalidByteHistogram"],{"0xFE":39})
        self.assertIsNone(row["pointerSpanMax"])
        self.assertNotIn("Secret",str(data))


if __name__=="__main__":
    unittest.main()
