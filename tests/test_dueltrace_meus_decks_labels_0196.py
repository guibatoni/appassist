"""Meus Decks naming contract — user-facing labels, no data/route migration."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class MyDecksLabelsTests(unittest.TestCase):
    def test_all_customer_facing_saved_deck_labels_are_portuguese(self):
        page=(ROOT/"web/components/desktop/saved-decks-page.tsx").read_text("utf8")
        menu=(ROOT/"web/components/shell/sidebar.tsx").read_text("utf8")
        decks=(ROOT/"web/components/desktop/decks-page.tsx").read_text("utf8")
        for source in (page,menu,decks):
            self.assertNotIn("Decks Salvos",source)
            self.assertNotIn("loadout",source.lower())
        self.assertIn(">Meus Decks</h1>",page)
        self.assertIn('label: "Meus Decks"',menu)
        self.assertIn(">Meus Decks</Link>",decks)

    def test_internal_route_and_saved_snapshot_ids_are_unchanged(self):
        # The UI name changes without invalidating bookmarks or saved decks.
        page=(ROOT/"web/app/decks-salvos/page.tsx").read_text("utf8")
        self.assertIn('page="decks-salvos"',page)
        source=(ROOT/"scanner/dueltrace_memory_cards.py").read_text("utf8")
        self.assertIn('"manual-"+fp',source)

    def test_translated_navigation_label_matches_new_name(self):
        translations=(ROOT/"web/lib/i18n-extra.ts").read_text("utf8")
        self.assertIn('"Meus Decks": {',translations)
        self.assertIn('"en": "My Decks"',translations)

if __name__=="__main__":
    unittest.main()
