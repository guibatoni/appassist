"""Restauração da leitura do Assistente antigo para ISOs não-X15.

A leitura do endereço legado pode sugerir pontos, mas só é EXPERIMENTAL.
Sem LP confirmado e duas alterações de contadores, não exibir número/RANK.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))

from dueltrace_rank_legacy_probe import (
    classify_legacy_transition, start_legacy_trial, update_legacy_trial
)
from dueltrace_rank_live import RULES

BASE={
    "turns":0, "effective_attacks":0,"defense_wins":0,
    "face_down":0,"spells":0,"traps":0,
    "cards_used":0,"remaining_lp":8000,
    "fusions":0,"equips":0
}
SHA="a"*64


class LegacyProbeTests(unittest.TestCase):
    def test_idle_poll_does_not_count_as_two_events(self):
        trial=start_legacy_trial(SHA,1234,BASE)
        for _ in range(12):
            self.assertEqual(update_legacy_trial(trial,SHA,1234,dict(BASE)),
                             ("observing",0))
        self.assertEqual(trial["events"],0)

    def test_two_coherent_changes_unlock_only_experimental_candidate(self):
        trial=start_legacy_trial(SHA,1234,BASE)
        next1={**BASE,"spells":1}
        next2={**next1,"turns":1}
        self.assertEqual(update_legacy_trial(trial,SHA,1234,next1),("observing",1))
        self.assertEqual(update_legacy_trial(trial,SHA,1234,next1),("observing",1))
        self.assertEqual(update_legacy_trial(trial,SHA,1234,next2),("candidate",2))
        self.assertEqual(update_legacy_trial(trial,SHA,1234,next2),("candidate",2))
        self.assertTrue(trial["confirmed"])

    def test_lp_change_is_observable_not_a_binding_proof(self):
        trial=start_legacy_trial(SHA,1234,BASE)
        self.assertEqual(update_legacy_trial(
            trial,SHA,1234,{**BASE,"remaining_lp":7200}),("observing",1))

    def test_pid_and_iso_switch_invalidate_trial(self):
        trial=start_legacy_trial(SHA,1234,BASE)
        self.assertEqual(update_legacy_trial(trial,"b"*64,1234,BASE),("invalid",0))
        self.assertEqual(update_legacy_trial(trial,SHA,9876,BASE),("invalid",0))

    def test_negative_counters_and_large_jumps_rejected(self):
        for bad in (
            {**BASE,"turns":3},
            {**BASE,"spells":15},
            {**BASE,"effective_attacks":-1},
            {**BASE,"cards_used":9},
            {**BASE,"remaining_lp":25000},
            {**BASE,"spells":True},
            {**BASE,"not_a_rank_counter":1}
        ):
            with self.subTest(bad=bad):
                self.assertEqual(classify_legacy_transition(BASE,bad),"invalid")
        self.assertEqual(classify_legacy_transition(BASE,BASE),"stable")
        self.assertEqual(classify_legacy_transition(BASE,{**BASE,"turns":1}),"event")

    def test_counters_cannot_decrease_except_lp(self):
        previous={**BASE,"turns":2,"spells":1}
        self.assertEqual(classify_legacy_transition(previous,{**previous,"turns":1}),"invalid")
        self.assertEqual(classify_legacy_transition(previous,{**previous,"spells":0}),"invalid")

    def test_required_metrics_not_silently_missing(self):
        self.assertEqual(frozenset(BASE),frozenset(RULES))
        with self.assertRaises(ValueError):
            start_legacy_trial(SHA,1234,{"turns":1})


if __name__=="__main__":
    unittest.main()
