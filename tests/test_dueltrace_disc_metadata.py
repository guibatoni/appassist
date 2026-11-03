"""Regressões da leitura de descrição SLUS e paletas WA.

Dados completamente sintéticos: a suite NUNCA distribui imagens de ROM.
"""
from __future__ import annotations

import sys
import struct
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))

from dueltrace_disc_metadata import (
    CARD_COUNT,DESC_POINTERS,DESC_DATA,DESC_BANK_END,FONT_GLYPHS,
    WA_FRAME_CLUT_BASE,FRAME_VARIANTS,
    _decode_psx_text,extract_descriptions,inspect_frame_palettes,
    effect_hint_from_description,
)


def synthetic_slus():
    exe=bytearray(FONT_GLYPHS+93*4)
    for code,word in enumerate((0x8260,0x8261,0x8262,0x8263,0x8264),1):
        struct.pack_into("<H",exe,FONT_GLYPHS+code*4,word)
    for cid in range(1,CARD_COUNT+1):
        offset=0x1B1200+(cid-1)*11
        struct.pack_into("<H",exe,DESC_POINTERS+cid*2,offset-DESC_DATA)
        exe[offset:offset+9]=bytes((1,2,3,4,5,0,1,2,0xFF))
    return bytes(exe)


def synthetic_wa():
    length=WA_FRAME_CLUT_BASE+14*512
    data=bytearray(length)
    for row in FRAME_VARIANTS.values():
        pos=WA_FRAME_CLUT_BASE+(row-240)*512
        for n in range(256):
            # RGB555 palette indices with plenty of variation.
            struct.pack_into("<H",data,pos+n*2,((n&31)|((n>>2&31)<<5)|((n>>3&31)<<10)))
    return bytes(data)


class DiscMetadataTests(unittest.TestCase):
    def test_slus_extracts_722_texts_with_id_and_provenance(self):
        extracted,report=extract_descriptions(synthetic_slus())
        self.assertEqual(len(extracted),722)
        self.assertEqual(report["recognized"],722)
        self.assertEqual(report["status"],"texto_extraido_layout_fm_com_verificacao_estrutural")
        self.assertEqual(extracted[1]["description_source"],"SLUS_014.11:tabela_descricoes")
        self.assertEqual(extracted[722]["description_offset"],0x1B1200+721*11)
        self.assertFalse(any("effect_text" in row for row in extracted.values()))

    def test_slus_rejects_corrupt_offsets_and_no_texts(self):
        invalid=bytearray(synthetic_slus())
        struct.pack_into("<H",invalid,DESC_POINTERS+12*2,0xFFFF)
        results,status=extract_descriptions(bytes(invalid))
        self.assertEqual(results,{})
        self.assertEqual(status["status"],"ponteiro_fora_do_banco")
        results,status=extract_descriptions(b"\x00"*1024)
        self.assertEqual(results,{})
        self.assertEqual(status["status"],"slus_menor_que_layout")

    def test_description_tokens_only_supported_commands(self):
        chars=[0,0x8260,0x8261,0x8262,0x8263,0x8264]
        txt=_decode_psx_text(b"\x01\x02\xFE\xF8\x0A\x01\x03\xFF",chars)
        self.assertIsNotNone(txt)
        self.assertIn("\n",txt)
        self.assertIsNone(_decode_psx_text(b"\x01\xF8\xFF",chars))
        self.assertIsNone(_decode_psx_text(b"\x01\xFD\xFF",chars))

    def test_effect_hint_only_if_explicit_marker_is_present(self):
        tagged=effect_hint_from_description("<Effect> Attack again.")
        self.assertEqual(tagged["effect_hint_trigger"],"effect")
        self.assertFalse(tagged["effect_hint_verified_in_game"])
        self.assertIn("nao_validacao",tagged["effect_hint_source"].replace("sem_validacao_de_execucao","nao_validacao"))
        self.assertIsNone(effect_hint_from_description("A strong monster."))
        self.assertIsNone(effect_hint_from_description("Destroy a monster."))
        self.assertIsNone(effect_hint_from_description("x"*401))

    def test_real_wa_colors_are_not_misrepresented_as_frame_bitmap(self):
        palettes,meta=inspect_frame_palettes(synthetic_wa())
        self.assertEqual(meta["status"],"paletas_lidas_layout_fm")
        self.assertEqual(len(palettes),6)
        self.assertEqual(palettes["magia"]["vram_row"],249)
        self.assertRegex(palettes["normal"]["accent"],r"^#[0-9a-f]{6}$")
        self.assertIn("geometria",meta["warning"])
        self.assertNotIn("png",str(meta).lower())

    def test_wa_missing_or_uniform_palette_is_rejected(self):
        self.assertFalse(inspect_frame_palettes(b"short")[0])
        bad=bytes(WA_FRAME_CLUT_BASE+14*512)
        data,meta=inspect_frame_palettes(bad)
        self.assertEqual(data,{})
        self.assertEqual(meta["status"],"paletas_uniformes_ou_modificadas")


if __name__=="__main__":
    unittest.main()
