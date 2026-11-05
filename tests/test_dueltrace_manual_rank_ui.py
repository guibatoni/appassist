"""Regressão da interface da calculadora de RANK no desktop Windows.

Não precisa de ISO, emulador nem dados pessoais. A fórmula é testada no
test_dueltrace_spoils_manual.py; aqui conferimos o caminho UI -> API existente.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]


class ManualRankUiContractTests(unittest.TestCase):
    def test_manual_rank_is_available_on_home_without_ram_binding(self):
        page=(ROOT/"web/components/desktop/desktop-page.tsx").read_text(encoding="utf-8")
        self.assertIn("function ManualRankCalculator({sha}",page)
        self.assertIn('<ManualRankCalculator key={sha??"sem-iso"} sha={sha}/>',page)
        self.assertIn("api.calculate_spoils(counters,victory)",page)
        self.assertIn("Selecione uma ISO na Biblioteca de Mods antes de calcular.",page)
        self.assertIn("rank?.status??\"Conectando ao ePSXe…\"",page)
        self.assertIn("Estimativa manual, não é um RANK confirmado",page)

    def test_ten_spoils_fields_and_three_victories_are_present(self):
        page=(ROOT/"web/components/desktop/desktop-page.tsx").read_text(encoding="utf-8")
        fields=(
            "turns","effective_attacks","defense_wins","face_down",
            "spells","traps","cards_used","remaining_lp","fusions","equips",
        )
        for field in fields:
            with self.subTest(field=field):
                self.assertIn('key:"'+field+'"',page)
        for victory in ("lp","deckout","exodia"):
            with self.subTest(victory=victory):
                self.assertIn('<option value="'+victory+'">',page)
        self.assertIn(r"/^\d{1,5}$/.test(raw)",page)

    def test_manual_engine_and_api_still_use_verified_formula(self):
        bridge=(ROOT/"scanner/dueltrace_web_bridge.py").read_text(encoding="utf-8")
        adapter=(ROOT/"scanner/dueltrace_web_security.py").read_text(encoding="utf-8")
        self.assertIn("return calculate_manual_spoils(counters,victory,sha)",bridge)
        self.assertIn("return self._bridge.calculate_spoils(counters,victory)",adapter)


if __name__=="__main__":
    unittest.main()
