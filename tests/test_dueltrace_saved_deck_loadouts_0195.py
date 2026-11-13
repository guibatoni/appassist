"""Saved Decks loadout workflow and searchable full fusion catalogue."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))
from dueltrace_deck_library import fusion_pairs_for_deck
from dueltrace_memory_cards import MemoryCardStore
from test_dueltrace_memory_and_deck_tabs import SHA, memory_bytes


class DeckLoadoutTests(unittest.TestCase):
    def test_user_saved_deck_is_named_and_listed_without_writing_ps1_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            card=root/"epsxe000.mcr"
            original=memory_bytes(list(range(1,41)))
            card.write_bytes(original)
            store=MemoryCardStore(root/"DUELTRACE_DATA")
            store.select(SHA,card)
            created=store.save_snapshot(SHA,"Meu loadout farm")
            self.assertTrue(created["saved"])
            self.assertTrue(created["id"].startswith("manual-"))
            library=store.read(SHA)
            names={deck["id"]:deck for deck in library["saved"]}
            self.assertEqual(names[created["id"]]["name"],"Meu loadout farm")
            self.assertEqual(names[created["id"]]["ids"],list(range(1,41)))
            self.assertEqual(names[created["id"]]["source"],"user_snapshot")
            self.assertEqual(card.read_bytes(),original)

    def test_fusion_search_can_reach_beyond_old_first_80_rows(self):
        ids=list(range(1,41))
        recipes=[{"a":a,"b":b,"result":((a+b)%722)+1,
                  "validation":"verificado"} for a in ids for b in ids if a<b]
        card_names={i:{"name":"Carta "+str(i)} for i in range(1,81)}
        default=fusion_pairs_for_deck(ids,recipes,card_names)
        full=fusion_pairs_for_deck(ids,recipes,card_names,max_results=820)
        self.assertEqual(full["total"],780)
        self.assertEqual(len(default["rows"]),80)
        self.assertEqual(len(full["rows"]),780)
        self.assertTrue(any(row["nameA"]=="Carta 39" for row in full["rows"]))
        bridge=(ROOT/"scanner/dueltrace_web_bridge.py").read_text("utf8")
        self.assertIn("fusion_pairs_for_deck(ids,recipes,cards,max_results=820)",bridge)

    def test_save_action_opens_the_dedicated_saved_deck_route(self):
        component=(ROOT/"web/components/desktop/decks-page.tsx").read_text("utf8")
        self.assertIn("api.save_current_deck(name.trim())",component)
        self.assertIn('router.push("/decks-salvos"',component)
        self.assertIn("encodeURIComponent(response.id)",component)
        self.assertIn("filteredCards.map(card=>",component)
        self.assertIn('aria-label="Pesquisar carta no deck"',component)
        self.assertIn("<DeckFusionGallery",component)
        page=(ROOT/"web/app/decks-salvos/page.tsx").read_text("utf8")
        self.assertIn('page="decks-salvos"',page)
        main=(ROOT/"web/components/desktop/desktop-page.tsx").read_text("utf8")
        self.assertIn('page==="decks-salvos"',main)
        nav=(ROOT/"web/components/shell/sidebar.tsx").read_text("utf8")
        self.assertIn('href: "/decks-salvos"',nav)
        self.assertIn('pathname === href || pathname.startsWith(href + "/")',nav)

    def test_loadout_page_searches_deck_names_and_its_card_names(self):
        component=(ROOT/"web/components/desktop/saved-decks-page.tsx").read_text("utf8")
        self.assertIn('const requested=new URLSearchParams(window.location.search).get("deck")',component)
        self.assertIn("entry.ids.some(id=>normalize",component)
        self.assertIn("api.get_deck_library(selectedId)",component)
        self.assertIn("CardFace",component)
        self.assertIn("<DeckFusionGallery",component)
        self.assertIn("Esta visualização não altera o deck do ePSXe",component)

    def test_fusion_gallery_includes_3_clickable_thumbnails_and_all_mode(self):
        source=(ROOT/"web/components/desktop/deck-fusion-gallery.tsx").read_text("utf8")
        for feature in ("row.nameA","row.nameB","row.nameResult",
                        'value="all"',"CardFace",
                        "onCardClick(card.id)","shown.length",
                        "onChange={e=>setQuery(e.target.value)}"):
            with self.subTest(feature=feature):
                self.assertIn(feature,source)
        self.assertIn("[1,5,10,20,50,100,200]",source)


if __name__=="__main__":
    unittest.main()
