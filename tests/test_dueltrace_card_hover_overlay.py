"""Regressões da janela de detalhes por clique em Biblioteca/Fusões/Drops.

Testes de contrato visual: não dependem de WebView ou imagens comerciais.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODAL = (ROOT / "web/components/desktop/card-hover-preview.tsx").read_text("utf-8")
PAGE = (ROOT / "web/components/desktop/desktop-page.tsx").read_text("utf-8")
DROPS = (ROOT / "web/components/desktop/drops-page.tsx").read_text("utf-8")
CLIENT = (ROOT / "web/lib/desktop.ts").read_text("utf-8")
BRIDGE = (ROOT / "scanner/dueltrace_web_bridge.py").read_text("utf-8")
SECURITY = (ROOT / "scanner/dueltrace_web_security.py").read_text("utf-8")


class CardDetailDialogTests(unittest.TestCase):
    def test_click_only_opens_card_details_without_hover_or_mouse_leave(self):
        for source in (PAGE, DROPS):
            self.assertIn('onClick=', source)
            self.assertIn('<CardHoverPreview selection={preview} sha={sha} cards={cards}', source)
            self.assertNotIn('onMouseEnter={event=>onPreview(', source)
            self.assertNotIn('onMouseLeave={()=>onPreview(null)}', source)
            self.assertNotIn('onFocus={event=>onPreview(', source)
            self.assertNotIn('pinned:true', source)
        self.assertIn('onClick={()=>setPreview({card})}', PAGE)
        self.assertIn('onClick={()=>onPreview({card:displayed})}', PAGE)
        self.assertIn('onClick={()=>onPreview({card,fallbackDrop:row})}', DROPS)
        self.assertNotIn('CARD_PREVIEW_DELAY_MS', MODAL)
        self.assertNotIn('onMouseLeave', MODAL)
        self.assertIn('role="dialog"', MODAL)
        self.assertIn('aria-modal="true"', MODAL)
        self.assertIn('document.body.style.overflow="hidden"', MODAL)

    def test_clickable_suggestions_stay_open_with_back_history(self):
        self.assertIn('const [history,setHistory]', MODAL)
        self.assertIn('setHistory(previous=>', MODAL)
        self.assertIn('setHistory(old=>old.length>1?old.slice(0,-1):old)', MODAL)
        self.assertIn('Voltar para a carta anterior', MODAL)
        self.assertIn('onClick={()=>navigate(id,name)}', MODAL)
        self.assertIn('cardById.get(id)', MODAL)
        self.assertIn('cardById=useMemo(()=>new Map(cards.map(card=>[card.id,card]))', MODAL)
        self.assertIn('if(event.key==="Escape")', MODAL)
        self.assertIn('event.key==="Backspace"&&event.altKey', MODAL)
        self.assertIn('previous.slice(-19)', MODAL)
        self.assertIn('closeButton.current?.focus()', MODAL)

    def test_five_material_and_five_result_suggestions(self):
        self.assertIn('api.get_card_fusion_paths(cardId)', MODAL)
        self.assertIn('data.romSha===sha&&data.cardId===cardId', MODAL)
        self.assertIn('fusions.materialRows.slice(0,5)', MODAL)
        self.assertIn('fusions.resultRows.slice(0,5)', MODAL)
        self.assertIn('Fusões usando esta carta como material', MODAL)
        self.assertIn('Fusões que resultam nesta carta', MODAL)
        self.assertIn('cardLink(row.partnerId,row.partnerName)', MODAL)
        self.assertIn('cardLink(row.resultId,row.resultName)', MODAL)
        self.assertIn('cardLink(row.materialAId,row.materialAName)', MODAL)
        self.assertIn('cardLink(row.materialBId,row.materialBName)', MODAL)
        self.assertIn('materialTotal', MODAL)
        self.assertIn('resultTotal', MODAL)
        self.assertIn('def??"—"', MODAL)

    def test_mod_data_is_bound_and_no_other_iso_details_leak(self):
        self.assertIn('card.descriptionSource&&card.description?.trim()', MODAL)
        self.assertIn('card.effectSource&&card.effect?.trim()', MODAL)
        self.assertIn('data.romSha===sha&&data.cardId===cardId', MODAL)
        self.assertIn('api.get_card_drop_sources(cardId)', MODAL)
        self.assertIn('row.chancePercent.toLocaleString', MODAL)
        self.assertIn('card.id===selection.card.id', MODAL)
        self.assertIn('cardArtHd(sha,card.id)', MODAL)
        self.assertIn('cardArt(sha,card.id)', MODAL)
        self.assertIn('onError={()=>setSource(old=>old==="hd"?"original":"none")}', MODAL)
        self.assertIn('/__art_hd__/', CLIENT)
        self.assertNotIn('sourceOffset', MODAL)
        self.assertNotIn('result.source', MODAL)

    def test_new_local_endpoint_is_capability_protected(self):
        self.assertIn('def get_card_fusion_paths(self, card_id):', BRIDGE)
        self.assertIn('def get_card_fusion_paths(self, credential, card_id):', SECURITY)
        self.assertIn('self._authorize(credential)', SECURITY)
        self.assertIn('get_card_fusion_paths(cardId: number)', CLIENT)
        self.assertIn('native.get_card_fusion_paths(token, cardId)', CLIENT)
        self.assertIn('"materialRows": materials[:5]', BRIDGE)
        self.assertIn('"resultRows": results[:5]', BRIDGE)


if __name__ == "__main__":
    unittest.main()
