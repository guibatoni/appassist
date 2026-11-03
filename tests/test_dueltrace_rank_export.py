"""Exportação de evidências RANK sem conteúdo privado ou arquivos do jogo."""
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from dueltrace_rank_export import build_rank_evidence_report


class RankExportTests(unittest.TestCase):
    def setUp(self):
        self.profile={
            "rom_sha256":"a"*64,
            "exe_sha256":"b"*64,
            "wa_sha256":"c"*64,
            "scan_result_dir":r"C:\Users\User\Secrets\game.bin",
            "token":"MY_PRIVATE_TOKEN",
            "drops_provenance":{"table_count":117},
            "rank_points":{"available":True,"table_sha256":"d"*64,
                           "structure_verified":True,"first_offset":15360000,
                           "repeat_stride":6144,
                           "rules":{"criterion_01":[{"below":5,"points":12}]}},
            "rank_mips_evidence":{"status":"mips_patterns_found",
                                  "candidates":[{"pc":"0x80012040"}]},
        }
        self.observations=[{
            "duel_id":"duel-000001","rom_sha256":"a"*64,
            "opponent_id":1,"card_id":200,"observed_rank":"Z-POW",
            "observed_points":95,"victory_type":"lp",
            "rank_snapshot":{"projected_score":95,"projected_rank":"Z-POW",
                             "counters":{"remaining_lp":8000,"other_secret":"X"}},
            "source_path":"C:/private-user-folder",
        }]
        self.traces=[{
            "duel_id":"duel-000001","traceSha256":"e"*64,
            "executionEvidence":True,
            "executedCandidates":[{"pc":"0x80012040","hits":11}],
            "rankTableEvidence":{"tableReadsObserved":True,"matchedPairs":5,
                                 "private_data":"DO_NOT_EXPORT"},
            "raw_log":"secret ROM bytes",
        }]

    def test_report_whitelists_fields_and_digest_is_stable(self):
        summary={"mappingConsistency":"corroborated","assignmentCount":1,
                 "mappingHypotheses":[],"suspectedMappings":{},
                 "mismatches":[]}
        first=build_rank_evidence_report(self.profile,self.observations,
                                          self.traces,summary)
        second=build_rank_evidence_report(self.profile,self.observations,
                                           self.traces,summary)
        self.assertEqual(first["report_sha256"],second["report_sha256"])
        self.assertEqual(first["drop_tables_validated"],117)
        self.assertEqual(first["duels"][0]["projected_score"],95)
        self.assertTrue(first["traces"][0]["wa_table_reads_observed"])
        self.assertFalse(first["mips"]["rank_routine_confirmed"])
        encoded=json.dumps(first)
        for secret in ("C:\\","C:/private","MY_PRIVATE_TOKEN",
                       "other_secret","secret ROM","DO_NOT_EXPORT"):
            self.assertNotIn(secret,encoded)

    def test_malformed_sha_and_profile_rejected(self):
        for payload in ({"rom_sha256":"nope"},
                        {"rom_sha256":"G"*64},
                        {"rom_sha256":None}):
            with self.assertRaises(ValueError):
                build_rank_evidence_report(payload,[],[],{})
        with self.assertRaises(ValueError):
            build_rank_evidence_report(None,[],[],{})


if __name__=="__main__":
    unittest.main()
