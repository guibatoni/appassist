"""Alpha customer UX contract: readable library, safe controls and paging.

These static contracts protect the intentional separation between user-facing
views and private engineering diagnostics; they do not replace Windows UI tests.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/"web/components/desktop/desktop-page.tsx")
DROPS=(ROOT/"web/components/desktop/drops-page.tsx")
POPOUT=(ROOT/"web/components/desktop/floating-tools.tsx")
SIDEBAR=(ROOT/"web/components/shell/sidebar.tsx")

class CustomerUiTests(unittest.TestCase):
    def test_mods_are_limited_to_four_cards_and_customer_actions(self):
        src=UI.read_text(encoding="utf-8")
        mods=src.split("function Mods(",1)[1].split("function CardDropSourcesPanel(",1)[0]
        route=src.split("export function DesktopPage(",1)[1]
        self.assertIn('["Cartas",mod.cards]',mods)
        self.assertIn('["Fusões"',mods)
        self.assertIn('["Oponentes"',mods)
        self.assertIn('["Drops"',mods)
        self.assertIn('setSearch(e.target.value)',mods)
        self.assertIn("rename_mod(",mods)
        self.assertIn("remove_mod(",mods)
        self.assertIn("A ISO original permanecerá no computador",mods)
        self.assertIn("Ativar mod",mods)
        self.assertIn("Atualizar dados",mods)
        for hidden in ("LiveDiagnosticsPanel sha=", "StructuralMatrixExplorer mod=",
                       "WindowEvidenceForm mod=","Comparar ISOs","Auditar ISO"):
            with self.subTest(hidden=hidden):
                self.assertNotIn(hidden,mods+route)
        self.assertNotIn('Calculadora em janela',route)

    def test_rank_panel_calibrates_in_backend_not_customer_ui(self):
        src=UI.read_text(encoding="utf-8")
        panel=src.split("function RankPanel(",1)[1].split("function Home(",1)[0]
        self.assertIn("api.get_rank_auto()",panel)
        self.assertIn("Abrir visor em pop-up",panel)
        self.assertNotIn("api.calibrate_rank()",panel)
        self.assertNotIn("Calibrar calculadora",panel)
        bridge=(ROOT/"scanner/dueltrace_web_bridge.py").read_text(encoding="utf-8")
        self.assertIn("self._rank_experimental_sha=sha",bridge)
        self.assertIn('and fields["turns"]>=1',bridge)
        self.assertIn('0<fields["remaining_lp"]<=32766',bridge)
        self.assertIn("def confirm_rank_lp(",bridge)

    def test_cards_fusions_drops_have_page_sizes_between_10_and_50(self):
        src=UI.read_text(encoding="utf-8")
        drops=DROPS.read_text(encoding="utf-8")
        self.assertGreaterEqual(src.count("[10,20,30,40,50]"),2)
        self.assertIn("[10,20,30,40,50]",drops)
        self.assertIn('c.effect??""',src)
        self.assertIn('c.description??""',src)
        self.assertIn("page*pageSize",src)
        self.assertIn("offset,pageSize,sort,cardType",src)
        self.assertIn("offset,pageSize,sort,cardType,rankFilter",drops)
        self.assertNotIn('result.status}</p>',drops)
        self.assertNotIn('row.weight}/2048',drops)

    def test_fusion_tips_show_names_and_artwork_with_no_egyptian_ornament(self):
        src=UI.read_text(encoding="utf-8")
        popup=POPOUT.read_text(encoding="utf-8")
        aside=SIDEBAR.read_text(encoding="utf-8")
        self.assertIn("CardThumbnail card={part.card}",src)
        self.assertIn("CardThumbnail card={cardsById.get(item.result)",src)
        self.assertIn("FusionTipCard label=\"Material\"",popup)
        self.assertIn("FusionTipCard label=\"Resultado\"",popup)
        self.assertIn('alt={card?.name??"Carta"}',popup)
        self.assertNotIn("function EyeOfHorus",aside)
        self.assertNotIn("40, 64, 88, 56, 36",aside)


if __name__=="__main__":
    unittest.main()
