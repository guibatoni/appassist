"""Testes da sincronização do nome das cartas no painel real (widgets simulados)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))

from overlay_card_labels import CardLabelSync, card_text


class FakeWidget:
    def __init__(self,children=None):
        self.children=list(children or [])
    def winfo_exists(self):
        return True
    def winfo_class(self):
        return "Frame"
    def winfo_children(self):
        return self.children


class FakeLabel(FakeWidget):
    def __init__(self,text):
        super().__init__()
        self.text=text
    def winfo_class(self):
        return "Label"
    def cget(self,prop):
        assert prop == "text"
        return self.text
    def configure(self,**kwargs):
        self.text=kwargs["text"]


class FakeCanvas(FakeWidget):
    def __init__(self,labels):
        super().__init__()
        self.items=dict(enumerate(labels,1))
    def winfo_class(self):
        return "Canvas"
    def find_all(self):
        return tuple(self.items)
    def type(self,index):
        return "text"
    def itemcget(self,index,prop):
        assert prop == "text"
        return self.items[index]
    def itemconfigure(self,index,**kwargs):
        self.items[index]=kwargs["text"]


def snapshot(cards):
    return {"ready":True,"features":{"nomes_cartas":True},"cards":cards}


def record(name):
    return {"name":name,"atk":1200,"def":1000}


class CardLabelTests(unittest.TestCase):
    def test_no_profile_no_unverified_names(self):
        self.assertEqual(card_text("Carta #123 (ID somente)",{}),"Carta #123 (ID somente)")
        self.assertEqual(card_text("Carta #123 (ID somente)",{456:record("Wrong")}),
                         "Carta #123 (ID somente)")
        self.assertEqual(card_text("Carta #123 (ID somente)",{123:record("Carta #123")}),
                         "Carta #123 (ID somente)")

    def test_mapped_cards_replace_only_id_placeholder(self):
        cards={123:record("Mago Negro"),420:record("Dragão de Teste")}
        self.assertEqual(card_text("Carta #123 (ID somente)",cards),"Mago Negro (#123)")
        self.assertEqual(card_text("Carta #420 (ID somente)",cards),"Dragão de Teste (#420)")
        self.assertEqual(card_text("ID da carta #123",cards),"ID da carta #123")

    def test_live_redraw_and_switch_profile(self):
        label=FakeLabel("Carta #123 (ID somente)")
        no_card=FakeLabel("Carta #999 (ID somente)")
        root=FakeWidget([label,no_card])
        renderer=CardLabelSync(root,roots=(root,))
        renderer.use_snapshot(snapshot({123:record("Carta do Original")}))
        self.assertEqual(label.text,"Carta do Original (#123)")
        self.assertEqual(no_card.text,"Carta #999 (ID somente)")
        # O overlay antigo substitui texto a cada atualização do duelo.
        label.text="Carta #123 (ID somente)"
        renderer.refresh()
        self.assertEqual(label.text,"Carta do Original (#123)")
        # Troca de perfil: nunca manter nome do mod anterior.
        renderer.use_snapshot(snapshot({123:record("Nome de outro mod")}))
        self.assertEqual(label.text,"Nome de outro mod (#123)")
        renderer.use_snapshot(snapshot({420:record("Outra Carta")}))
        self.assertEqual(label.text,"Carta #123 (ID somente)")

    def test_canvas_text_also_supported(self):
        canvas=FakeCanvas(["Carta #420 (ID somente)","PONTOS: 101"])
        root=FakeWidget([canvas])
        sync=CardLabelSync(root,roots=(root,))
        sync.use_snapshot(snapshot({420:record("Carta 420")}))
        self.assertEqual(canvas.items[1],"Carta 420 (#420)")
        self.assertEqual(canvas.items[2],"PONTOS: 101")
        sync.use_snapshot({"ready":False})
        self.assertEqual(canvas.items[1],"Carta #420 (ID somente)")

    def test_does_not_modify_other_fields(self):
        label=FakeLabel("Tipo desconhecido — ATK / — DEF")
        rank=FakeLabel("101 pontos — fórmula X15 não validada")
        root=FakeWidget([label,rank])
        sync=CardLabelSync(root,roots=(root,))
        sync.use_snapshot(snapshot({123:record("Novo Nome")}))
        self.assertEqual(label.text,"Tipo desconhecido — ATK / — DEF")
        self.assertEqual(rank.text,"101 pontos — fórmula X15 não validada")


if __name__ == "__main__":
    unittest.main()
