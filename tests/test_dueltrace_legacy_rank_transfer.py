"""Paridade com Assistente_X15_v10_5_ISO_INTEGRADA (motor v8/v9).

A fonte enviada pelo usuário confirma +0 byte assinado, contadores u8,
LP s16le, cartas s8, tabela de dez métricas e faixas X15 50/95.
A validação de RAM real continua separada.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from scanner_multiiso import X15_SHA
from dueltrace_rank_system import (
    X15_RANKS, CLASSIC_RANKS, available_ranks,
    rank_label_for_existing_score, rank_system, pool_index_for_rank,
)
from dueltrace_rank_live import (
    RULES, decode_rank_record, decode_rank_result_adjustment,
    project_spoils_with_adjustment, project_lp_win_rank, read_rank_candidate,
)
from test_dueltrace_rank_live import make_record, FakeKernel

# Limiar exclusivo e pontos extraídos de tabela_spoils_x15.json do assistente.
LEGACY_V105 = {
    "turns":[(5,12),(9,8),(29,0),(33,-8),(32767,-12)],
    "effective_attacks":[(2,4),(4,2),(10,0),(20,-2),(32767,-4)],
    "defense_wins":[(2,0),(6,-10),(10,-20),(15,-30),(32767,-40)],
    "face_down":[(1,0),(11,-2),(21,-4),(31,-6),(32767,-8)],
    "spells":[(1,2),(4,-4),(7,-8),(10,-12),(32767,-16)],
    "traps":[(1,2),(3,-8),(5,-16),(7,-24),(32767,-32)],
    "cards_used":[(9,15),(13,12),(33,0),(37,-5),(32767,-7)],
    "remaining_lp":[(100,-7),(1000,-5),(7000,0),(8000,4),(32767,6)],
    "fusions":[(1,4),(5,0),(10,-4),(15,-8),(32767,-12)],
    "equips":[(1,4),(5,0),(10,-4),(15,-8),(32767,-12)],
}


class LegacyX15TransferTests(unittest.TestCase):
    def test_all_ten_rules_match_v105_source_byte_for_byte_numeric(self):
        self.assertEqual(RULES,LEGACY_V105)

    def test_record_offsets_and_signed_fields_match_v105(self):
        raw=bytearray(make_record(lp=11300,turns=4,spells=3,cards_used=8))
        raw[0]=0xD8  # -40 assinado: deck-out
        raw[2]=3    # ataques efetivos, u8
        raw[3]=2    # defesa, u8
        raw[4]=1    # face down
        raw[6]=2    # armadilhas
        raw[8]=4    # fusões
        raw[9]=5    # equipamentos
        record=decode_rank_record(bytes(raw))
        self.assertEqual(record,{
            "turns":4,"effective_attacks":3,"defense_wins":2,
            "face_down":1,"spells":3,"traps":2,
            "fusions":4,"equips":5,"remaining_lp":11300,
            "cards_used":8,
        })
        self.assertEqual(decode_rank_result_adjustment(bytes(raw)),-40)

    def test_marker_2_and_d8_only_after_stable_double_read(self):
        raw=bytearray(make_record(lp=8000,turns=1))
        self.assertIsNone(decode_rank_result_adjustment(bytes(raw)))
        raw[0]=2
        self.assertEqual(decode_rank_result_adjustment(bytes(raw)),2)
        result=read_rank_candidate(kernel=FakeKernel([bytes(raw),bytes(raw)]),pids=[1234])
        self.assertTrue(result["ready"])
        self.assertEqual(result["result_adjustment"],2)
        raw[0]=0xD8
        result=read_rank_candidate(kernel=FakeKernel([bytes(raw),bytes(raw)]),pids=[1234])
        self.assertEqual(result["result_adjustment"],-40)
        wrong=bytearray(raw);wrong[0]=0
        result=read_rank_candidate(kernel=FakeKernel([bytes(raw),bytes(wrong)]),pids=[1234])
        self.assertFalse(result["ready"])
        self.assertIsNone(result["counters"])
        self.assertIsNone(decode_rank_result_adjustment(b""))
        self.assertIsNone(decode_rank_result_adjustment(bytes(31)))
        raw[0]=5
        self.assertIsNone(decode_rank_result_adjustment(bytes(raw)))

    def test_spoils_101_lp_59_deckout_139_exodia_same_ten_rules(self):
        base=decode_rank_record(make_record())
        self.assertEqual(project_lp_win_rank(base)["score"],101)
        lp=project_spoils_with_adjustment(base,2)
        deck=project_spoils_with_adjustment(base,-40)
        exodia=project_spoils_with_adjustment(base,40)
        self.assertEqual((lp["score"],deck["score"],exodia["score"]),
                         (101,59,139))
        self.assertEqual(lp["breakdown"],deck["breakdown"])
        self.assertEqual(deck["breakdown"],exodia["breakdown"])
        self.assertFalse(deck["final"])
        for bad in (None,True,0,-41,"-40"):
            with self.assertRaises(ValueError):
                project_spoils_with_adjustment(base,bad)

    def test_all_original_labels_and_x15_only_three_labels(self):
        original_sha="a"*64
        self.assertEqual(rank_system(original_sha),"classic")
        self.assertEqual(rank_system(X15_SHA),"x15")
        self.assertEqual(len(CLASSIC_RANKS),10)
        self.assertEqual(len(X15_RANKS),3)
        scores={
            101:"S-POW",95:"S-POW",90:"S-POW",89:"A-POW",
            80:"A-POW",79:"B-POW",70:"B-POW",69:"C-POW",
            60:"C-POW",59:"D-POW",50:"D-POW",49:"D-TEC",
            40:"D-TEC",39:"C-TEC",30:"C-TEC",29:"B-TEC",
            20:"B-TEC",19:"A-TEC",10:"A-TEC",9:"S-TEC",
            0:"S-TEC",-30:"S-TEC",
        }
        for score,label in scores.items():
            with self.subTest(score=score):
                self.assertEqual(rank_label_for_existing_score(original_sha,score),label)
                self.assertIn(label,available_ranks(original_sha))
                self.assertNotEqual(label,"Z-POW")
        self.assertEqual(rank_label_for_existing_score(X15_SHA,95),"Z-POW")
        self.assertEqual(rank_label_for_existing_score(X15_SHA,94),"S-POW")
        self.assertEqual(rank_label_for_existing_score(X15_SHA,50),"S-POW")
        self.assertEqual(rank_label_for_existing_score(X15_SHA,49),"S-TEC")

    def test_names_cannot_unlock_x15_categories_or_drop_pools(self):
        for fake in ("Remaster X15","X15.iso","fm13","original","b"*64,None):
            with self.subTest(sha=fake):
                self.assertEqual(rank_system(fake),"classic")
                self.assertEqual(len(available_ranks(fake)),10)
                self.assertNotIn("Z-POW",available_ranks(fake))
                with self.assertRaises(ValueError):
                    pool_index_for_rank(fake,"Z-POW")
        self.assertEqual(pool_index_for_rank(X15_SHA,"Z-POW"),0)
        with self.assertRaises(ValueError):
            pool_index_for_rank(X15_SHA,"A-POW")


if __name__=="__main__":
    unittest.main()
