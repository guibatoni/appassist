"""Contratos de UI pública: Mods em lista e prévia de drops nas Fusões.

Sem usar ROM, dados pessoais nem execução do ePSXe.
"""
import unittest
from pathlib import Path

PAGE=Path(__file__).resolve().parents[1]/"web"/"components"/"desktop"/"desktop-page.tsx"


class PublicUiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=PAGE.read_text(encoding="utf-8")
        cls.mods=cls.source.split("function Mods({mods,sha,onRefresh,configured}:{",1)[1].split("function CardDropSourcesPanel(",1)[0]
        cls.fusions=cls.source.split("function FusionIllustration(",1)[1].split("export function DesktopPage(",1)[0]

    def test_mods_use_one_column_disclosure_list_with_status_and_actions(self):
        mods=self.mods
        self.assertIn('className="mt-4 space-y-2"',mods)
        self.assertIn("aria-expanded={open}",mods)
        self.assertIn("aria-controls={",mods)
        self.assertIn("setExpandedSha(open?null:mod.sha256)",mods)
        self.assertIn("ChevronDown",mods)
        self.assertIn('rotate-180',mods)
        self.assertIn('>Ativo</span>',mods)
        self.assertIn('"Ativar mod"',mods)
        self.assertIn('Atualizar dados',mods)
        self.assertIn('Adicionar mod',mods)

    def test_public_mod_details_hide_experiments_raw_paths_and_dev_diagnostics(self):
        for forbidden in (
            "rankMipsCandidates","rankOffset","Offset WA:","dropCandidateTables",
            "dropCandidateEntries","WA_MRG + SLUS","chosenExecutable",
            "chosenWa","waSelectionMethod","Ollama:","Arquivos indexados:",
            "Evidências e próximas investigações",
            "get_mod_scan_diagnostic","investigate(mod","rankBinaryVerified",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,self.mods)
        # Os métodos de análise continuam no backend e não são expostos como UI.
        self.assertNotIn(">{mod.sha256",self.mods)
        self.assertIn("api.scan_sources(mod.sha256)",self.mods)
        self.assertIn('mod.requiresReview',self.mods)
        self.assertNotIn("CardMatchPanel mods=",self.mods)

    def test_fusion_preview_is_mouse_and_keyboard_accessible(self):
        source=self.fusions
        self.assertIn("onMouseEnter={event=>onPreview(",source)
        self.assertIn("onMouseLeave={()=>onPreview(null,null)}",source)
        self.assertIn("onFocus={event=>onPreview(",source)
        self.assertIn("onBlur={()=>onPreview(null,null)}",source)
        self.assertIn('role="tooltip"',source)
        self.assertIn('backdrop-blur-lg',source)
        self.assertIn('transition-all duration-200',source)
        self.assertIn('Onde conseguir',source)
        self.assertIn('MonsterStats card={hoveredCard.card}',source)

    def test_hover_preview_tracks_own_card_is_bigger_and_stays_within_viewport(self):
        source=self.fusions
        self.assertIn("previewAnchor.current=anchor",source)
        self.assertIn("const rect=anchor.getBoundingClientRect()",source)
        self.assertIn("const width=panel.offsetWidth",source)
        self.assertIn("const height=panel.offsetHeight",source)
        self.assertIn("rect.left+rect.width/2-width/2",source)
        self.assertIn("window.innerWidth-width-margin",source)
        self.assertIn("const above=rect.top-height-gap",source)
        self.assertIn("window.innerHeight-height-margin",source)
        self.assertIn('window.addEventListener("scroll",place,true)',source)
        self.assertIn('window.addEventListener("resize",place)',source)
        self.assertIn("ref={previewElement}",source)
        self.assertIn("style={previewPosition??{left:0,top:0}}",source)
        self.assertIn("w-[min(92vw,440px)]",source)
        self.assertIn("sm:w-44",source)
        self.assertIn("<CardThumbnail card={hoveredCard.card} sha={sha} expanded/>",source)
        self.assertNotIn("fixed bottom-4 right-4",source)
        self.assertIn("pointer-events-none",source)

    def test_card_drops_are_fetched_for_current_mod_and_exact_card_id(self):
        source=self.fusions
        self.assertIn("api.get_card_drop_sources(hoveredId)",source)
        self.assertIn("data.romSha===sha&&data.cardId===hoveredId",source)
        self.assertIn("drops?.available",source)
        self.assertIn("dropRows.slice(0,4)",source)
        self.assertIn("row.eligibleRanks.join",source)
        self.assertIn("row.chancePercent.toLocaleString",source)
        self.assertNotIn("drops.source",source)
        self.assertNotIn("As imagens só aparecem quando o scanner",source)


if __name__=="__main__":
    unittest.main()
