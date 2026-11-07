"""Alpha release smoke contracts. No copyrighted assets or emulator required."""
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))
from dueltrace_alpha_reward_pools import discover_alpha_reward_pools


class AlphaReleaseContractTests(unittest.TestCase):
    def test_popout_static_routes_and_source_mode_exist(self):
        paths=(
            "web/app/ferramentas/calculadora/page.tsx",
            "web/app/ferramentas/fusoes/page.tsx",
            "web/components/desktop/floating-tools.tsx",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue((ROOT/path).is_file())
        desktop=(ROOT/"scanner/dueltrace_web_desktop.py").read_text(encoding="utf-8")
        self.assertIn('url="about:blank"',desktop)
        self.assertIn('child.events.loaded+=secure_loaded',desktop)
        self.assertIn('child.load_url(url+"ferramentas/"+kind+"/")',desktop)
        ui=(ROOT/"web/components/desktop/desktop-page.tsx").read_text(encoding="utf-8")
        self.assertIn('open_tool_window("calculadora")',ui)
        self.assertIn('open_tool_window("fusoes")',ui)
        self.assertIn('Ocultar dicas',ui)

    def test_unidentified_reward_layout_never_associates_drops(self):
        rejected=discover_alpha_reward_pools(b"not a game resource")
        self.assertFalse(rejected["available"])
        self.assertFalse(rejected["opponentIdentityVerified"])
        self.assertFalse(rejected["mayActivateDrops"])


if __name__=="__main__":
    unittest.main()
