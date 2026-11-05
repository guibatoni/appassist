"""Regressão da mesma prévia sobre carta nas abas Fusões e Drops."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SHARED=ROOT/"web/components/desktop/card-hover-preview.tsx"
FUSION=ROOT/"web/components/desktop/desktop-page.tsx"
DROPS=ROOT/"web/components/desktop/drops-page.tsx"


class SharedCardPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.overlay=SHARED.read_text(encoding="utf-8")
        cls.fusions=FUSION.read_text(encoding="utf-8")
        cls.drops=DROPS.read_text(encoding="utf-8")

    def test_preview_waits_one_second_for_hover_or_selection(self):
        source=self.overlay
        self.assertIn("const CARD_PREVIEW_DELAY_MS=1000",source)
        self.assertIn("window.setTimeout(()=>{",source)
        self.assertIn("},CARD_PREVIEW_DELAY_MS)",source)
        self.assertIn("return()=>window.clearTimeout(timer)",source)
        self.assertIn("setRevealed(null)",source)
        self.assertIn("if(!selection)return",source)
        self.assertIn("if(selection.anchor.isConnected)setRevealed(selection)",source)
        self.assertIn("revealed===selection?revealed:null",source)
        self.assertIn("if(!mounted||!activeSelection||!card)return null",source)

    def test_background_and_lookup_start_only_when_preview_is_visible(self):
        source=self.overlay
        self.assertIn("const card=activeSelection?.card??null",source)
        self.assertIn("const cardId=card?.id??null",source)
        self.assertIn("if(!sha||cardId===null)return",source)
        self.assertIn("if(!mounted||!activeSelection||!card)return null",source)
        self.assertIn("const anchor=activeSelection.anchor",source)
        self.assertIn("setPosition(null)",source)
        self.assertIn('event.key==="Escape"',source)
        # Este componente é chamado em Fusões e Drops; não há tempos diferentes.
        for page in (self.fusions,self.drops):
            self.assertIn('<CardHoverPreview selection={preview} sha={sha}',page)

    def test_drops_preview_uses_full_card_details_from_active_iso(self):
        # Mesma coleção utilizada na Biblioteca de Cartas e nas Fusões.
        self.assertIn('<DropsPage sha={state?.activeSha??null} cards={state?.cards??[]}/>',self.fusions)
        self.assertIn("export function DropsPage({sha,cards}:",self.drops)
        self.assertIn("new Map(cards.map(card=>[card.id,card]))",self.drops)
        self.assertIn("cardsById.get(row.cardId)??null",self.drops)
        self.assertIn("cardDetails?.id===row.cardId?cardDetails",self.drops)

    def test_shows_verified_description_and_effect_without_exposing_file_paths(self):
        source=self.overlay
        self.assertIn("card.descriptionSource&&card.description?.trim()",source)
        self.assertIn("card.effectSource&&card.effect?.trim()",source)
        self.assertIn('duplicateText?"Descrição / efeito":"Descrição"',source)
        self.assertIn('>Efeito</h4>',source)
        self.assertIn('duplicateText',source)
        self.assertIn('Descrição e efeito não disponíveis para esta carta.',source)
        self.assertIn('whitespace-pre-line break-words',source)
        self.assertNotIn('{card.descriptionSource}',source)
        self.assertNotIn('{card.effectSource}',source)
        self.assertIn("CARD_PREVIEW_DELAY_MS=1000",source)
        self.assertIn("Onde conseguir",source)

    def test_overlay_centers_on_selected_card_not_corner(self):
        source=self.overlay
        self.assertIn("createPortal(<>",source)
        self.assertIn("document.body",source)
        self.assertIn("selection.anchor",source)
        self.assertIn("anchor.getBoundingClientRect()",source)
        self.assertIn("const centerX=rect.left+rect.width/2",source)
        self.assertIn("const centerY=rect.top+rect.height/2",source)
        self.assertIn("centerX-width/2",source)
        self.assertIn("centerY-height/2",source)
        self.assertIn("window.innerWidth-width-margin",source)
        self.assertIn("window.innerHeight-height-margin",source)
        self.assertNotIn("bottom-4 right-4",source)
        self.assertIn("ResizeObserver(place)",source)

    def test_background_darkens_without_blocking_mouse(self):
        source=self.overlay
        self.assertIn('fixed inset-0 z-[90] bg-[#020713]/75',source)
        self.assertIn('pointer-events-none fixed z-[100]',source)
        self.assertIn('role="tooltip"',source)
        self.assertIn('event.key==="Escape"',source)
        self.assertIn('onClose()',source)
        self.assertIn('onMouseLeave={()=>onPreview(null)}',self.fusions)
        self.assertIn('onMouseLeave={()=>onPreview(null)}',self.drops)

    def test_fusions_and_drops_share_identical_preview(self):
        for source in (self.fusions,self.drops):
            self.assertIn('import {CardHoverPreview} from "./card-hover-preview"',source)
            self.assertIn('<CardHoverPreview selection={preview} sha={sha}',source)
            self.assertIn('onFocus={event=>onPreview(',source)
            self.assertIn('onMouseEnter={event=>onPreview(',source)
        self.assertNotIn('WA offset:',self.drops)

    def test_retrieves_validated_drops_for_active_iso(self):
        source=self.overlay
        self.assertIn('api.get_card_drop_sources(cardId)',source)
        self.assertIn('data.cardId===cardId&&data.romSha===sha',source)
        self.assertIn('matched&&result.available',source)
        self.assertIn('rows.slice(0,4)',source)
        self.assertIn('row.eligibleRanks.join(" / ")',source)
        self.assertIn('row.chancePercent.toLocaleString("pt-BR"',source)
        self.assertNotIn('result.source',source)
        self.assertNotIn('sourceOffset',source)

    def test_preview_is_larger_than_list_thumbnail_and_reset_when_filter_changes(self):
        self.assertIn('w-40 shrink-0 sm:w-48',self.overlay)
        self.assertIn('sizes="192px"',self.overlay)
        self.assertIn('w-[min(94vw,500px)]',self.overlay)
        self.assertIn('useEffect(()=>{setPreview(null)},[sha,query,offset,sort,cardType])',self.fusions)
        self.assertIn('setPreview(null)',self.drops)
        self.assertIn('fallbackDrop:row',self.drops)


if __name__=="__main__":
    unittest.main()
