"""Regressions for click-only card information dialogs across all four card views."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
DIALOG=(ROOT/"web/components/desktop/card-info-dialog.tsx").read_text(encoding="utf-8")
PAGE=(ROOT/"web/components/desktop/desktop-page.tsx").read_text(encoding="utf-8")
DROPS=(ROOT/"web/components/desktop/drops-page.tsx").read_text(encoding="utf-8")
HOME=PAGE.split("function Home(",1)[1].split("function CardMatchPanel(",1)[0]
LIBRARY=PAGE.split("function Library(",1)[1].split("function FusionIllustration(",1)[0]
FUSIONS=PAGE.split("function FusionIllustration(",1)[1].split("export function DesktopPage(",1)[0]


class CardClickDialogTests(unittest.TestCase):
    def test_every_card_page_uses_one_click_only_dialog(self):
        for source in (HOME,LIBRARY,FUSIONS,DROPS):
            with self.subTest(page="home" if source is HOME else
                              "library" if source is LIBRARY else
                              "fusions" if source is FUSIONS else "drops"):
                self.assertIn("<CardInfoDialog selection={preview} sha={sha}",source)
                self.assertNotIn("onMouseEnter=",source)
                self.assertNotIn("onMouseLeave=",source)
                self.assertNotIn("onDoubleClick=",source)
                self.assertNotIn("pinned:true",source)
                self.assertNotIn("anchor:event.currentTarget",source)
                self.assertNotIn("CARD_PREVIEW_DELAY_MS",source)

    def test_hand_and_fusion_tips_open_by_click(self):
        self.assertIn('onClick={()=>{if(card)setPreview({card})}}',HOME)
        self.assertIn('onClick={()=>{if(part.card)setPreview({card:part.card})}}',HOME)
        self.assertIn('disabled={!card}',HOME)
        self.assertIn('disabled={!part.card}',HOME)
        self.assertIn('onClose={()=>setPreview(null)}',HOME)

    def test_library_fusions_and_drops_use_click_actions(self):
        self.assertIn('onClick={()=>setPreview({card})}',LIBRARY)
        self.assertIn('onClick={()=>onPreview({card:displayed})}',FUSIONS)
        self.assertIn('onClick={()=>onPreview({card,fallbackDrop:row})}',DROPS)
        self.assertIn('onPreview={setPreview}',DROPS)
        self.assertIn('onPreview={setPreview}',FUSIONS)
        self.assertIn('onClose={()=>setPreview(null)}',LIBRARY)

    def test_dialog_is_interactive_accessible_and_closes_intentionally(self):
        self.assertIn('export function CardInfoDialog(',DIALOG)
        self.assertIn('role="dialog" aria-modal="true"',DIALOG)
        self.assertIn('tabIndex={-1} ref={dialogRef}',DIALOG)
        self.assertIn('onClick={onClose}',DIALOG)
        self.assertIn('aria-label="Fechar informações da carta"',DIALOG)
        self.assertIn('event.key==="Escape"',DIALOG)
        self.assertIn('event.key==="Tab"',DIALOG)
        self.assertIn('dialogRef.current?.focus()',DIALOG)
        self.assertIn('prior.focus()',DIALOG)
        self.assertIn('pointer-events-auto dueltrace-scroll',DIALOG)
        self.assertNotIn('role="tooltip"',DIALOG)
        self.assertNotIn('setRevealed(',DIALOG)
        self.assertNotIn('CARD_PREVIEW_DELAY_MS',DIALOG)
        self.assertNotIn('selection.anchor',DIALOG)

    def test_preserves_description_effect_drop_and_fusion_details(self):
        for expected in (
            'card.descriptionSource&&card.description?.trim()',
            'card.effectSource&&card.effect?.trim()',
            'whitespace-pre-line break-words text-xs leading-relaxed',
            'api.get_card_drop_sources(cardId)',
            'api.get_card_fusions(cardId,fusionPage*8,8,fusionSort)',
            'data.cardId===cardId&&data.romSha===sha',
            'data.romSha===sha&&data.cardId===cardId',
            'rows.slice(0,4)',
            'Possíveis fusões',
            'fusion.partnerName',
            'fusion.resultName',
            'fusion.atk??"—"',
            'aria-label="Ordenar fusões possíveis"',
            'aria-label="Mais fusões"',
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected,DIALOG)
        self.assertNotIn("line-clamp-4",DIALOG)
        self.assertNotIn("sourceOffset",DIALOG)
        self.assertNotIn("{card.descriptionSource}",DIALOG)

    def test_modal_is_centered_and_responsive_without_intercepting_hover(self):
        for expected in (
            'createPortal(<>',
            'fixed inset-0 z-[90] bg-[#020713]/75',
            'pointer-events-none fixed inset-0 z-[100]',
            'max-h-[calc(100dvh-24px)]',
            'overflow-y-auto',
            'w-[min(calc(100vw-24px),500px)]',
        ):
            self.assertIn(expected,DIALOG)
        self.assertNotIn("getBoundingClientRect()",DIALOG)
        self.assertIn('fallbackDrop:row',DROPS)
        self.assertIn('new Map(cards.map(card=>[card.id,card]))',DROPS)
        self.assertIn("setPreview(null)",DROPS)


if __name__=="__main__":
    unittest.main()
