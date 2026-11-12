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
        cls.mods=cls.source.split("function Mods({mods,sha,onRefresh,configured}:{",1)[1].split("function Library(",1)[0]
        cls.fusions=cls.source.split("function FusionIllustration(",1)[1].split("export function DesktopPage(",1)[0]

    def test_mods_use_one_column_disclosure_list_with_status_and_actions(self):
        mods=self.mods
        self.assertIn('className="mt-4 space-y-3"',mods)
        self.assertIn("aria-expanded={open}",mods)
        self.assertIn("aria-controls={",mods)
        self.assertIn("setExpandedSha(open?null:mod.sha256)",mods)
        self.assertIn("ChevronDown",mods)
        self.assertIn('rotate-180',mods)
        self.assertIn('● Ativo</span>',mods)
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
        self.assertIn("desktopApi()!.scan_sources(mod.sha256)",self.mods)
        self.assertIn('mod.requiresReview',self.mods)
        self.assertNotIn("CardMatchPanel mods=",self.mods)

    def test_fusions_use_shared_persistent_click_dialog(self):
        source=self.fusions
        self.assertIn("onClick={()=>onPreview({card:displayed})}",source)
        self.assertNotIn("onMouseEnter={event=>onPreview(",source)
        self.assertNotIn("onMouseLeave={()=>onPreview(null)}",source)
        self.assertNotIn("onFocus={event=>onPreview(",source)
        self.assertIn('onPreview={setPreview}',source)
        self.assertIn('<CardHoverPreview selection={preview} sha={sha} cards={cards}',source)
        self.assertNotIn('role="tooltip"',source)
        self.assertNotIn("fixed bottom-4 right-4",source)

    def test_old_fusion_card_overlay_replaced_with_shared_component(self):
        source=self.fusions
        self.assertIn("setPreview(null)",source)
        self.assertIn("const [preview,setPreview]",source)
        self.assertNotIn("previewElement",source)
        self.assertNotIn("previewPosition",source)
        self.assertNotIn("getBoundingClientRect",source)

    def test_fusion_search_scope_filters_by_result_or_material(self):
        source=self.fusions
        self.assertIn('const [searchScope,setSearchScope]',source)
        self.assertIn('aria-label="Pesquisar fusões em"',source)
        self.assertIn('<option value="all">Resultado ou material</option>',source)
        self.assertIn('<option value="result">Resultado final da fusão</option>',source)
        self.assertIn('<option value="material">Material da fusão</option>',source)
        self.assertIn('aria-label="Buscar fusões por nome ou ID"',source)
        self.assertIn('api.get_fusions(query,offset,pageSize,sort,cardType,searchScope)',source)
        self.assertIn('setSearchScope("all")',source)
        self.assertIn('[sha,query,searchScope,offset,sort,cardType,pageSize]',source)
        self.assertIn('setOffset(0)',source)

    def test_fusions_keep_exact_source_card_and_sha(self):
        source=self.fusions
        self.assertIn("onClick={()=>onPreview({card:displayed})}",source)
        self.assertIn('<CardHoverPreview selection={preview} sha={sha}',source)
        self.assertIn("useEffect(()=>{setPreview(null)},[sha,query,searchScope,offset,sort,cardType])",source)



if __name__=="__main__":
    unittest.main()
