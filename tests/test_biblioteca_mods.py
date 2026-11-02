"""Testes da Biblioteca de Mods e integração segura.

Não precisam de ISO do jogo, tela gráfica ou rede.
"""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))

from biblioteca_mods import preview_model
from investigador_iso import fusion_triplet_hypotheses
from instalar_biblioteca import patch_source, START
from ia_local import minimal_evidence, validate_suggestion


class BibliotecaTests(unittest.TestCase):
    def test_preview_only_validated_features(self):
        p={
            "name":"ROM desconhecida",
            "supported_features":{"cards":True,"opponents":True,"drops":False,
                                  "fusions":False,"ranks":False,"scoring":False},
            "cards":[{"id":1,"name":"Carta A","atk":1000,"def":1000}],
            "opponents":[{"id":1,"name":"Mago"}],
            "drops":[{"card_id":1}],
            "fusion_recipes":[{"a":1,"b":2,"result":3}],
        }
        m=preview_model(p)
        self.assertEqual(len(m["cards"]),1)
        self.assertEqual(len(m["opponents"]),1)
        self.assertEqual(m["drops"],[])
        self.assertEqual(m["fusions"],[])
        self.assertFalse(m["rank_confirmed"])

    def test_fusion_hypotheses_are_not_verified(self):
        # 30 triplas u16 são suficientes para gerar uma hipótese, nunca fato.
        import struct
        payload=b"\xff"*80+b"".join(struct.pack("<HHH",i,i+1,i+2) for i in range(1,31))+b"\xff"*24
        candidates=fusion_triplet_hypotheses(payload,min_run=24)
        self.assertTrue(candidates)
        self.assertTrue(all("NÃO VALIDADA" in c["status"] for c in candidates))
        self.assertGreaterEqual(candidates[0]["entries"],24)

    def test_random_noise_gives_no_fusions(self):
        self.assertEqual(fusion_triplet_hypotheses(b"\xff"*1200),[])

    def test_ai_proposals_never_change_verified_data(self):
        report={"file":"teste.iso","hash_rom":"a"*64,
                "candidates":{"fusion_tables_u16":[{"offset":120,"entries":35,"source_file":"SLUS_014.11"}]},
                "uncertainties":[{"field":"fusoes","status":"não_extraídas"}]}
        evidence=minimal_evidence(report)
        response={"resumo":"Estrutura potencial", "prioridades":["Verificar com o jogo"],
                  "indices_candidatos_fusao":[0,99,True,"0"],
                  "alertas":["Não foi validada"]}
        filtered=validate_suggestion(response,evidence)
        self.assertEqual(filtered["indices_candidatos_fusao"],[0])
        self.assertFalse(filtered["verified_data_changed"])
        self.assertIn("NÃO VALIDADO",filtered["status"])

    def test_installer_injects_once_after_compact_panel(self):
        source = (
            "class App:\n"
            "    def __init__(self, root):\n"
            "        self.compact = CompactPanel(\n"
            "            root, self.cards, self.recipes\n"
            "        )\n"
            "        self.more = True\n"
        )
        patched=patch_source(source)
        ast.parse(patched)
        self.assertEqual(patch_source(patched),patched)
        self.assertEqual(patched.count(START),1)
        self.assertIn("self._multimod_library_bridge",patched)
        self.assertLess(patched.index(START),patched.index("self.more = True"))

    def test_installer_rejects_unknown_app_layout(self):
        with self.assertRaises(ValueError):
            patch_source("print('sem classe App')\n")


if __name__=="__main__":
    unittest.main()
