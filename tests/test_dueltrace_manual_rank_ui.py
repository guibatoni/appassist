"""Contrato da tela Início: mão, fusões e RANK automático, sem UI de diagnóstico."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
PAGE=ROOT/"web/components/desktop/desktop-page.tsx"


class CleanHomeRankUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page=PAGE.read_text(encoding="utf-8")
        cls.home=cls.page.split("function Home({sha,cards}:",1)[1].split(
            "function CardMatchPanel(",1)[0]
        cls.rank=cls.page.split("function RankPanel({sha}:",1)[1].split(
            "function Home({sha,cards}:",1)[0]

    def test_home_contains_only_hand_rank_and_fusions(self):
        self.assertIn('aria-label="Cartas na mão"',self.home)
        self.assertIn('<RankPanel sha={sha}/>',self.home)
        self.assertIn('aria-label="Dicas de fusões"',self.home)
        self.assertNotIn("ManualRankCalculator",self.page)
        self.assertNotIn("Calculadora manual de RANK",self.page)
        self.assertNotIn("manualRankMetrics",self.page)
        self.assertNotIn("sourceLabel(",self.home)

    def test_rank_is_continuously_automatic_without_calibration_button(self):
        self.assertIn("api.get_rank_auto()",self.rank)
        self.assertIn("window.setInterval(()=>void poll(),850)",self.rank)
        self.assertNotIn("api.calibrate_rank()",self.rank)
        self.assertNotIn("Calibrar calculadora",self.rank)
        self.assertIn("Abrir visor em pop-up",self.rank)
        self.assertIn("rank.score",self.rank)
        self.assertIn("rank.category",self.rank)
        self.assertNotIn("api.calculate_spoils",self.rank)
        self.assertNotIn("set_rank_experimental",self.rank)

    def test_home_hides_all_developer_diagnostics_and_raw_rank_status(self):
        for forbidden in (
            "Diagnóstico e ferramentas", "Diagnosticar ISO", "Reanalisar perfil",
            "Testar RANK ao vivo (experimental)", "Desativar teste RAM",
            "RANK automático não validado", "RAM antiga em teste",
            "mapeamento RAM", "rank?.status", "get_rank_diagnostic()",
            "capture_rank_prediction()", "rankMipsCandidates",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,self.rank)
        self.assertNotIn("Nenhuma confirmação de LP",self.rank)
        self.assertNotIn("diagnostic",self.rank.lower())
        self.assertNotIn('result.note',self.rank)
        self.assertNotIn('sourceLabel(',self.home)

    def test_backend_calculator_and_diagnostics_remain_available_for_developers(self):
        bridge=(ROOT/"scanner/dueltrace_web_bridge.py").read_text(encoding="utf-8")
        protected=(ROOT/"scanner/dueltrace_web_security.py").read_text(encoding="utf-8")
        self.assertIn("def calculate_spoils(",bridge)
        self.assertIn("def get_rank_diagnostic(",bridge)
        self.assertIn("def calibrate_rank(self):",bridge)
        self.assertIn("self.set_rank_experimental(True)",bridge)
        self.assertIn("return self._bridge.calibrate_rank()",protected)
        self.assertIn("return self._bridge.get_rank_auto()",protected)


if __name__=="__main__":
    unittest.main()
