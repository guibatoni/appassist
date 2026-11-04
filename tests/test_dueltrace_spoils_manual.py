"""Motor SPOILS da conversa antiga: testes sem RAM, ROM ou emulador."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from dueltrace_spoils_manual import calculate_manual_spoils
from scanner_multiiso import X15_SHA

CLASSIC="a"*64
BASE={
    "turns":4,"effective_attacks":1,"defense_wins":0,"face_down":0,
    "spells":0,"traps":0,"cards_used":8,"remaining_lp":8000,
    "fusions":0,"equips":0,
}


class SpoilsManualTests(unittest.TestCase):
    def test_lp_uses_base50_ten_categories_plus_two(self):
        result=calculate_manual_spoils(BASE,"lp",X15_SHA)
        self.assertEqual(result["basePoints"],50)
        self.assertEqual(result["victoryBonus"],2)
        self.assertEqual(result["score"],101)
        self.assertEqual(result["category"],"Z-POW")
        self.assertEqual(len(result["breakdown"]),10)
        self.assertEqual(sum(result["breakdown"].values()),49)
        self.assertFalse(result["verifiedInEmulator"])

    def test_deckout_and_exodia_use_same_rules_and_other_bonus(self):
        deck=calculate_manual_spoils(BASE,"deckout",X15_SHA)
        exodia=calculate_manual_spoils(BASE,"exodia",X15_SHA)
        self.assertEqual(deck["score"],59)
        self.assertEqual(deck["victoryBonus"],-40)
        self.assertEqual(exodia["score"],139)
        self.assertEqual(exodia["victoryBonus"],40)

    def test_same_numeric_score_different_iso_display(self):
        x15=calculate_manual_spoils(BASE,"lp",X15_SHA)
        original=calculate_manual_spoils(BASE,"lp",CLASSIC)
        self.assertEqual(x15["score"],original["score"])
        self.assertEqual(x15["category"],"Z-POW")
        self.assertEqual(original["category"],"S-POW")
        self.assertEqual(original["rankSystem"],"classic")

    def test_thresholds_do_not_change_while_recovering_old_spoils(self):
        from dueltrace_rank_system import rank_label_for_existing_score
        self.assertEqual(rank_label_for_existing_score(X15_SHA,95),"Z-POW")
        self.assertEqual(rank_label_for_existing_score(X15_SHA,90),"S-POW")
        self.assertEqual(rank_label_for_existing_score(X15_SHA,50),"S-POW")
        self.assertEqual(rank_label_for_existing_score(X15_SHA,49),"S-TEC")
        self.assertEqual(rank_label_for_existing_score(CLASSIC,50),"D-POW")
        # Registro histórico de partida "50 S-TEC" diverge do cutoff atual
        # e deve ser investigado em duelo, nunca mascarado pela calculadora.

    def test_effective_attacks_are_not_direct_attacks(self):
        row=dict(BASE,effective_attacks=2)
        expected=calculate_manual_spoils(BASE,"lp",X15_SHA)["score"]
        changed=calculate_manual_spoils(row,"lp",X15_SHA)["score"]
        self.assertEqual(expected-changed,2)

    def test_real_epsxe_b_pow_duel_screenshot_2026_11_04(self):
        """Dados das três telas Results of Duel: RANK B-POW real.

        Batoni: 5 turnos, 13 cartas usadas, 9500 LP, 1 ataque efetivo,
        0 vitórias defesa, 3 face-down, 0 magias, 0 traps,
        3 fusões, 0 equips. A tela mostra B-POW (não score numérico).
        A projeção anterior do DUELTRACE foi 76, classificação B-POW.
        """
        counters={
            "turns":5,"effective_attacks":1,"defense_wins":0,
            "face_down":3,"spells":0,"traps":0,
            "cards_used":13,"remaining_lp":9500,"fusions":3,"equips":0,
        }
        calculated=calculate_manual_spoils(counters,"lp",CLASSIC)
        self.assertEqual(calculated["breakdown"],{
            "turns":8, "effective_attacks":4, "defense_wins":0,
            "face_down":-2, "spells":2, "traps":2,
            "cards_used":0, "remaining_lp":6, "fusions":0, "equips":4,
        })
        self.assertEqual(sum(calculated["breakdown"].values()),24)
        self.assertEqual(calculated["score"],76)  # 50 base + 2 LP + 24
        self.assertEqual(calculated["category"],"B-POW")
        self.assertEqual(calculated["rankSystem"],"classic")
        self.assertFalse(calculated["verifiedInEmulator"])
        x15=calculate_manual_spoils(counters,"lp",X15_SHA)
        self.assertEqual(x15["score"],76)
        self.assertEqual(x15["category"],"S-POW")

    def test_rejects_invalid_or_missing_metrics_and_bonuses(self):
        for change in ({"turns":-1},{"turns":True},{"cards_used":256},
                       {"remaining_lp":32767},{"remaining_lp":1.5}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                calculate_manual_spoils({**BASE,**change},"lp",CLASSIC)
        for bad in (None, "other", "defeat", 0):
            with self.assertRaises(ValueError):
                calculate_manual_spoils(BASE,bad,CLASSIC)
        with self.assertRaises(ValueError):
            calculate_manual_spoils({},"lp",CLASSIC)


if __name__=="__main__":
    unittest.main()
