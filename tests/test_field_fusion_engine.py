"""Testa guardrails de campo: sem dados RAM comprovados, não sugerir fusões."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from field_fusion_engine import suggest_hand_field_fusions as suggest


class FieldSuggestionTests(unittest.TestCase):
    def setUp(self):
        self.sha="a"*64
        self.hand=[16,200,10,45,461]
        self.recipes=[(16,10,69),(10,16,69),(45,10,425),(45,461,33)]
        self.cards={69:{"name":"Thousand Dragon","atk":2400},
                    425:{"name":"Thunder Dragon","atk":1600}}
        self.field={"profile_sha256":self.sha,"ram_verified":True,
                    "side":"player","zone":"monster",
                    "slots":[{"slot":1,"card_id":10}]}

    def run_suggest(self,**kwargs):
        data={"rom_sha256":self.sha,"hand_ids":self.hand,
              "field_snapshot":self.field,"recipes":self.recipes,
              "cards":self.cards}
        data.update(kwargs)
        return suggest(**data)

    def test_no_fabricated_board_data(self):
        self.assertFalse(self.run_suggest(field_snapshot=None)["ready"])
        self.assertFalse(self.run_suggest(field_snapshot={
            **self.field,"ram_verified":False})["ready"])
        self.assertFalse(self.run_suggest(field_snapshot={
            **self.field,"profile_sha256":"b"*64})["ready"])
        self.assertFalse(self.run_suggest(field_snapshot={
            **self.field,"side":"opponent"})["ready"])
        self.assertFalse(self.run_suggest(field_snapshot={
            **self.field,"zone":"spell"})["ready"])

    def test_reject_invalid_field_slots_or_hand(self):
        for slotset in ([{"slot":5,"card_id":10}],
                        [{"slot":0,"card_id":722},{"slot":0,"card_id":10}],
                        [{"slot":0,"card_id":800}],
                        [{"slot":True,"card_id":10}],
                        [{"slot":0,"card_id":False}]):
            self.assertFalse(self.run_suggest(field_snapshot={
                **self.field,"slots":slotset})["ready"])
        self.assertFalse(self.run_suggest(hand_ids=[16,10])["ready"])

    def test_approved_pairs_only_deduplicated(self):
        x=self.run_suggest()
        self.assertTrue(x["ready"])
        self.assertEqual(x["field_cards"],[{"slot":1,"card_id":10}])
        self.assertEqual(x["total"],2)
        self.assertEqual([r["result_id"] for r in x["suggestions"]],[69,425])
        self.assertTrue(all(x["theoretical"] for x in x["suggestions"]))
        self.assertTrue(all(x["confirmation_recorded"] is False for x in x["suggestions"]))

    def test_no_recipe_means_no_prediction(self):
        x=self.run_suggest(recipes=[])
        self.assertEqual(x["suggestions"],[])
        self.assertTrue(x["ready"])


if __name__=="__main__":
    unittest.main()
