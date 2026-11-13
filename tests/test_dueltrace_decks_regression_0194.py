"""Regression for mistaken live deck and 15-block PS1/ePSXe save UI."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))

from dueltrace_web_bridge import DueltraceWebBridge
from dueltrace_memory_cards import MemoryCardStore

SHA="a"*64


class DeckProvenanceTests(unittest.TestCase):
    def make_bridge(self,tmp):
        catalog=Mock()
        catalog.home=Path(tmp)
        bridge=DueltraceWebBridge(catalog)
        profile={"rom_sha256":SHA,
                 "supported_features":{"cards":True,"fusions":True},
                 "cards":[{"id":i,"name":f"Card {i}","atk":100,"def":200}
                          for i in range(1,41)],
                 "fusion_recipes":[]}
        bridge._active=Mock(return_value=(
            {"sha256":SHA},{"display_name":"Mod Original"},profile))
        bridge._cards=Mock(return_value=profile["cards"])
        bridge._combined_fusion_recipes=Mock(return_value=([],False))
        bridge._memory_mod_name=Mock(return_value="Mod Original")
        return bridge

    def memory(self):
        return {"linked":True,"cardName":"epsxe000.mcr",
                "saveName":"BASLUS-01411-YUGIOH",
                "saveDisplayName":"Bloco 1","activeModName":"Original",
                "selectedBlock":1,"savePinned":True,
                "gameIntegrityVerified":True,
                "deckIds":list(range(1,41)),
                "saves":[{"block":1,"displayName":"Bloco 1"}],
                "blocks":[{"block":i,"status":"fm_valid" if i==1 else "empty",
                           "selectable":i==1,"label":"Save" if i==1 else "Livre",
                           "saveName":"BASLUS-01411-YUGIOH" if i==1 else None}
                          for i in range(1,16)],
                "saved":[],"status":"Save íntegro, dados do cartão."}

    def test_plausible_but_wrong_live_deck_must_not_override_saved_deck(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=self.make_bridge(tmp)
            tracker=Mock()
            tracker.running=True
            tracker.snapshot.return_value={"ready":True,"deckIds":[722]*40,
                                            "pid":123,"status":"guess"}
            app._background_live=tracker
            with patch.object(MemoryCardStore,"read",return_value=self.memory()):
                view=app.get_deck_library()
            self.assertEqual(view["deckIds"],list(range(1,41)))
            self.assertEqual(view["displayName"],"Deck gravado no Memory Card")
            self.assertEqual(view["deckSource"],"memory_card")
            self.assertEqual(view["deckCount"],40)
            self.assertEqual(len(view["blocks"]),15)
            self.assertFalse(view["liveDeckMatchesSave"])
            self.assertFalse(view["activeInEmulatorVerified"])
            self.assertEqual([row["id"] for row in view["cards"]],list(range(1,41)))

    def test_even_matching_ram_is_only_corrobation_not_unverified_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=self.make_bridge(tmp)
            tracker=Mock()
            tracker.running=True
            tracker.snapshot.return_value={"ready":True,
                                            "deckIds":list(range(1,41)),
                                            "matchesVerifiedSave":True}
            app._background_live=tracker
            with patch.object(MemoryCardStore,"read",return_value=self.memory()):
                view=app.get_deck_library()
            self.assertTrue(view["liveDeckMatchesSave"])
            self.assertFalse(view["activeInEmulatorVerified"])
            self.assertEqual(view["deckSource"],"memory_card")
            self.assertEqual(view["deckIds"],list(range(1,41)))
            self.assertIn("Memory Card",view["displayName"])

    def test_save_current_deck_cannot_persist_unconfirmed_ram_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=self.make_bridge(tmp)
            with (patch.object(MemoryCardStore,"save_snapshot",
                               return_value={"saved":True,"name":"Meu deck"}) as saved,
                  patch.object(MemoryCardStore,"save_live_snapshot") as unsafe):
                result=app.save_current_deck("Meu deck")
            self.assertTrue(result["saved"])
            saved.assert_called_once_with(SHA,"Meu deck")
            unsafe.assert_not_called()

    def test_invalid_or_missing_save_does_not_show_random_ram_cards(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=self.make_bridge(tmp)
            tracker=Mock()
            tracker.running=True
            tracker.snapshot.return_value={"ready":True,"deckIds":[9]*40}
            app._background_live=tracker
            no_save={**self.memory(),"deckIds":[],"gameIntegrityVerified":False,
                     "saveName":None,"selectedBlock":None}
            with patch.object(MemoryCardStore,"read",return_value=no_save):
                view=app.get_deck_library()
            self.assertEqual(view["deckCount"],0)
            self.assertEqual(view["deckIds"],[])
            self.assertFalse(view["liveDeckMatchesSave"])
            self.assertFalse(view["activeInEmulatorVerified"])

    def test_page_offers_other_card_and_physical_slots(self):
        view=(ROOT/"web/components/desktop/decks-page.tsx").read_text("utf8")
        self.assertIn("Selecionar outro Memory Card",view)
        self.assertIn("15 blocos físicos do Memory Card",view)
        self.assertIn("slot.selectable",view)
        self.assertIn("state.deckSource",view)
        self.assertNotIn("Leitura ao vivo confirmada na RAM",view)


if __name__=="__main__":
    unittest.main()
