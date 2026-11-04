"""Ollama opina apenas em pares de cartas já propostos pelo scanner local."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))

from dueltrace_card_match_ai import review_card_candidates


class FakeResponse:
    status=200
    def __init__(self,text):
        self.payload=json.dumps({"response":text}).encode("utf-8")
    def __enter__(self):return self
    def __exit__(self,*_args):return False
    def read(self,_n):return self.payload


class LocalCardAIReviewTests(unittest.TestCase):
    def setUp(self):
        self.source={
            "sourceSha":"a"*64,"targetSha":"b"*64,
            "rows":[
                {"sourceId":3,"targetId":33,
                 "sourceName":"Flower Wolf","targetName":"Wolf of Flowers",
                 "signals":["nome_parecido","atk_def_iguais"],
                 "confidence":"revisar","ambiguous":False},
                {"sourceId":4,"targetId":41,
                 "sourceName":"Autumn Queen","targetName":"Queen of Leaves",
                 "signals":["nome_parecido"],
                 "confidence":"revisar","ambiguous":True},
                {"sourceId":5,"targetId":61,
                 "sourceName":"Identical identity","targetName":"Identical identity",
                 "signals":["nome_exato","atk_def_iguais"],
                 "confidence":"alta","ambiguous":False},
            ]
        }

    def test_whitelists_existing_review_pairs_and_never_updates_profiles(self):
        result_payload=json.dumps({"revisoes":[
            {"id_origem":3,"id_destino":33,"parecer":"revisar",
             "motivo":"Nomes próximos, falta arte."},
            {"id_origem":999,"id_destino":888,"parecer":"manter_candidata",
             "motivo":"Criar ID inexistente"},
            {"id_origem":5,"id_destino":61,"parecer":"manter_candidata",
             "motivo":"par alto não era revisão"},
            {"id_origem":4,"id_destino":41,"parecer":"descartar",
             "motivo":"Sem evidência suficiente."},
        ]},ensure_ascii=False)
        requests=[]
        def fake_open(request,timeout):
            requests.append(request)
            self.assertEqual(timeout,45)
            return FakeResponse(result_payload)
        report=review_card_candidates(self.source,opener=fake_open)
        self.assertEqual(report["status"],"hipoteses_nao_validadas")
        self.assertEqual(report["analysed"],2)
        self.assertEqual(len(report["revisoes"]),2)
        self.assertEqual(
            {(row["sourceId"],row["targetId"]) for row in report["revisoes"]},
            {(3,33),(4,41)})
        self.assertFalse(report["verifiedInGame"])
        self.assertFalse(report["updatedProfiles"])
        self.assertEqual(len(requests),1)
        self.assertEqual(requests[0].full_url,"http://127.0.0.1:11434/api/generate")
        sent=json.loads(requests[0].data)
        self.assertFalse(sent["stream"])
        self.assertNotIn("Identical identity",sent["prompt"])
        self.assertEqual(self.source["rows"][0]["sourceId"],3)

    def test_no_ambiguous_pairs_never_contacts_ai(self):
        self.source["rows"]=[self.source["rows"][-1]]
        not_called=Mock(side_effect=AssertionError("Ollama should not run"))
        data=review_card_candidates(self.source,opener=not_called)
        self.assertEqual(data["status"],"sem_duvidas")
        not_called.assert_not_called()

    def test_malformed_response_cannot_create_matches(self):
        with self.assertRaises(ConnectionError):
            review_card_candidates(
                self.source,
                opener=lambda request,timeout:FakeResponse("{invalid json"))
        data=review_card_candidates(
            self.source,
            opener=lambda request,timeout:FakeResponse(
                json.dumps({"revisoes":[{"id_origem":3,
                                         "id_destino":999,
                                         "parecer":"manter_candidata"}]})))
        self.assertEqual(data["revisoes"],[])

    def test_invalid_model_rejected(self):
        with self.assertRaises(ValueError):
            review_card_candidates(self.source,model="model\ninject")


if __name__=="__main__":
    unittest.main()
