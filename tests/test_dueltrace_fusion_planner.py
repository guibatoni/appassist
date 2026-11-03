"""Casos adversariais de fusões consecutivas com dados inteiramente sintéticos."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scanner"))

from dueltrace_live_hand import build_fusion_index
from dueltrace_fusion_planner import plan_fusion_chains, describe_route


class FusionChainPlannerTests(unittest.TestCase):
    @staticmethod
    def example():
        recipes = [
            {"a":1,"b":2,"result":10,
             "validation":"extraida_sete_bancos_consistentes"},
            {"a":10,"b":3,"result":20,
             "validation":"extraida_sete_bancos_consistentes"},
            {"a":20,"b":4,"result":30,
             "validation":"observada_manualmente_no_jogo"},
            {"a":30,"b":5,"result":40,
             "validation":"observada_manualmente_no_jogo"},
            {"a":1,"b":3,"result":11,
             "validation":"extraida_sete_bancos_consistentes"},
            {"a":11,"b":2,"result":21,
             "validation":"extraida_sete_bancos_consistentes"},
        ]
        cards = {
            20:{"id":20,"name":"Fusão B","atk":1500},
            21:{"id":21,"name":"Fusão alternativa","atk":1800},
            30:{"id":30,"name":"Fusão C","atk":2200},
            40:{"id":40,"name":"Fusão final","atk":3000},
        }
        return build_fusion_index(recipes), cards

    def test_chains_three_to_five_cards_in_correct_order(self):
        index, cards = self.example()
        result = plan_fusion_chains([1,2,3,4,5],index,cards,limit=20)
        self.assertTrue(result["complete"])
        self.assertGreater(result["explored_states"],0)
        by_id = {item["result"]:item for item in result["routes"]}
        self.assertEqual(by_id[40]["used_slots"],[1,2,3,4,5])
        self.assertEqual([s["result"] for s in by_id[40]["steps"]],
                         [10,20,30,40])
        self.assertEqual(by_id[40]["cards_consumed"],5)
        self.assertEqual(by_id[40]["manual_steps"],2)
        self.assertFalse(by_id[40]["route_observed_in_game"])
        self.assertEqual(result["routes"][0]["result"],40)
        self.assertIn("resultado anterior",describe_route(by_id[40],cards))

    def test_play_order_is_not_confused_with_sorted_consumed_slots(self):
        idx=build_fusion_index([
            {"a":2,"b":4,"result":10},
            {"a":10,"b":1,"result":20},
        ])
        result=plan_fusion_chains([1,2,3,4,5],idx,{})
        route=next(r for r in result["routes"] if r["result"]==20)
        self.assertEqual(route["used_slots"],[1,2,4])
        self.assertEqual(route["slot_order"],[2,4,1])
        self.assertEqual([step["slot"] for step in route["steps"]],[4,1])

    def test_never_reuse_consumed_slot_even_with_repeated_card_ids(self):
        recipes=[
            {"a":4,"b":4,"result":10},
            {"a":10,"b":4,"result":20},
            {"a":10,"b":10,"result":30},
        ]
        index=build_fusion_index(recipes)
        result=plan_fusion_chains([4,4,4,7,8],index,{20:{"atk":500}})
        rows=result["routes"]
        self.assertTrue(any(r["result"]==20 for r in rows))
        self.assertFalse(any(r["result"]==30 for r in rows))
        for route in rows:
            self.assertEqual(len(route["used_slots"]),
                             len(set(route["used_slots"])))
            self.assertEqual(len(route["steps"]),
                             len(route["used_slots"])-1)

    def test_no_spurious_fusion_or_modified_hand(self):
        index,cards=self.example()
        hand=[1,2,3,4,5]
        original=hand[:]
        self.assertEqual(plan_fusion_chains(hand,{},cards)["routes"],[])
        plan_fusion_chains(hand,index,cards)
        self.assertEqual(hand,original)
        for invalid in (None,[],[1,2,3,4],[1,2,3,4,0],
                        [1,2,3,4,723],[1,2,3,4,True]):
            self.assertEqual(
                plan_fusion_chains(invalid,index,cards)["routes"],[])

    def test_truncation_is_clearly_flagged_not_marked_as_optimum(self):
        index={}
        hand=[1,2,3,4,5]
        for i in range(5):
            for j in range(i+1,5):
                index[(hand[i],hand[j])] = [
                    (r,"extraida_sete_bancos_consistentes")
                    for r in range(100,160)]
        report=plan_fusion_chains(hand,index,{},max_states=100)
        self.assertFalse(report["complete"])
        self.assertEqual(report["explored_states"],100)
        self.assertLessEqual(len(report["routes"]),12)

    def test_unknown_attack_last_and_repeated_calls_are_stable(self):
        idx=build_fusion_index([
            {"a":1,"b":2,"result":10},
            {"a":10,"b":3,"result":20},
            {"a":1,"b":3,"result":11},
            {"a":11,"b":2,"result":21},
        ])
        cards={20:{"atk":100},21:{"name":"No ATK"}}
        a=plan_fusion_chains([1,2,3,4,5],idx,cards)
        b=plan_fusion_chains([1,2,3,4,5],idx,cards)
        self.assertEqual(a,b)
        self.assertEqual([row["result"] for row in a["routes"]],[20,21])

    def test_individually_tested_steps_do_not_certify_whole_chain(self):
        idx=build_fusion_index([
            {"a":1,"b":2,"result":10,
             "validation":"observada_manualmente_no_jogo"},
            {"a":10,"b":3,"result":20,
             "validation":"observada_manualmente_no_jogo"},
        ])
        result=plan_fusion_chains([1,2,3,4,5],idx,{})
        route=result["routes"][0]
        self.assertTrue(route["all_steps_observed_individually"])
        self.assertFalse(route["route_observed_in_game"])

    def test_parameter_validation_and_filter(self):
        idx,cards=self.example()
        only_five=plan_fusion_chains([1,2,3,4,5],idx,cards,
                                      min_cards=5,max_cards=5)
        self.assertEqual([row["result"] for row in only_five["routes"]],[40])
        for bad in ({"min_cards":2},{"max_cards":6},{"limit":0},
                    {"max_states":99},{"min_cards":3.5}):
            with self.assertRaises(ValueError):
                plan_fusion_chains([1,2,3,4,5],idx,cards,**bad)


@unittest.skipUnless(sys.platform=="win32","GUI Tk requer Windows")
class FusionPlannerWindowTests(unittest.TestCase):
    def test_switch_pair_and_chain_views_and_clear_on_disconnect(self):
        import tempfile
        import tkinter as tk
        from auto_mods import ModCatalog
        from dueltrace_desktop import DueltraceDesktop
        with tempfile.TemporaryDirectory() as td:
            try:
                app=DueltraceDesktop(catalog=ModCatalog(Path(td)))
            except tk.TclError as exc:
                if "display" in str(exc).lower() or "screen" in str(exc).lower():
                    self.skipTest(str(exc))
                raise
            try:
                app.withdraw()
                app.update_idletasks()
                self.assertEqual(app.active_page,"inicio")
                index,cards=FusionChainPlannerTests.example()
                app._home_fusions=index
                app._home_cards={**{n:{"id":n,"name":f"Carta {n}"} for n in range(1,6)},
                                 **cards}
                app._render_live_hand({
                    "ready":True,"hand_ids":[1,2,3,4,5],"pid":1234,
                    "status":"Mão de teste"})
                self.assertGreater(len(app.home_fusion_tree.get_children()),0)
                self.assertEqual(app._home_fusion_mode,"pairs")
                app._set_home_fusion_mode("chains")
                app.update_idletasks()
                self.assertEqual(app._home_fusion_mode,"chains")
                values=[
                    app.home_fusion_tree.item(node)["values"]
                    for node in app.home_fusion_tree.get_children()]
                self.assertTrue(any("Fusão final" in str(row) for row in values))
                self.assertIn("rotas",app.home_fusion_count.get())
                app._render_live_hand({
                    "ready":False,"hand_ids":None,"pid":None,
                    "status":"ePSXe desconectado"})
                self.assertEqual(len(app.home_fusion_tree.get_children()),0)
                self.assertTrue(all(tile.card is None for tile in app.home_hand_tiles))
                app._set_home_fusion_mode("pairs")
                self.assertEqual(len(app.home_fusion_tree.get_children()),0)
            finally:
                app.destroy()


if __name__=="__main__":
    unittest.main()
