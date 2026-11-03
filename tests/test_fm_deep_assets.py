"""Testes sintéticos do layout clássico WA_MRG, sem dados comerciais do jogo."""
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
import fm_deep_assets as assets


def synthetic_wa():
    # Apenas 12 MiB em memória, preenchidos com amostras de índices e CLUT.
    data=bytearray(0xB90000)
    colors=[(i*2+1) & 31 | (((i*3+1)&31)<<5) | (((i*5+1)&31)<<10)
            for i in range(256)]
    for cid in (1,2):
        base=(assets.FIRST_CARD_SECTOR+(cid-1)*7)*2048
        for i in range(102*96):
            data[base+i]=i%32
        struct.pack_into("<256H",data,base+0x2640,*colors)
        start=(cid-1)*2048
        small=bytes(i%32 for i in range(40*32))
        data[start:start+1280]=small
        struct.pack_into("<64H",data,start+0x500,*colors[:64])
        data[base+0x2AE0:base+0x2AE0+0x580]=data[start:start+0x580]
    frame=assets.DUEL_IMAGE_START+2*assets.DUEL_COL_SIZE
    for y in range(assets.FRAME_H):
        p=frame+(assets.FRAME_V+y)*assets.FRAME_ROW_STRIDE
        for x in range(52):
            data[p+x]=(x+y)%64
    for idx in range(6):
        struct.pack_into("<256H",data,
                         assets.DUEL_CLUT_START+(idx+1)*256*2,*colors)
    return bytes(data)


class WAAssetTests(unittest.TestCase):
    def test_frame_index_by_type_not_id_or_name(self):
        self.assertEqual(assets.frame_index(0),0)
        self.assertEqual(assets.frame_index(19),0)
        self.assertEqual(assets.frame_index(20),1)
        self.assertEqual(assets.frame_index(23),1)
        self.assertEqual(assets.frame_index(21),2)
        self.assertEqual(assets.frame_index(22),3)
        self.assertIsNone(assets.frame_index(26))
        self.assertIsNone(assets.frame_index("Dragão"))

    def test_frames_use_8bit_original_256_color_cluts(self):
        wa=synthetic_wa()
        first=assets.decode_hand_frame(wa,0)
        second=assets.decode_hand_frame(wa,1)
        self.assertEqual(first.size,(52,60))
        self.assertEqual(second.size,(52,60))
        # Pixel x=51 e início da linha seguinte provam leitura de 52 bytes
        # por linha, em vez de nibbles 4bpp.
        self.assertNotEqual(first.getpixel((0,0)),first.getpixel((51,0)))
        self.assertNotEqual(first.getpixel((0,0)),first.getpixel((0,1)))

    def test_frame_decoder_and_invalid_palette_are_bounded(self):
        wa=synthetic_wa()
        im=assets.decode_hand_frame(wa,0)
        self.assertEqual(im.size,(52,60))
        self.assertNotEqual(im.getpixel((0,0)),im.getpixel((2,0)))
        with self.assertRaises(ValueError):
            assets.decode_hand_frame(wa,6)
        with self.assertRaises(ValueError):
            assets.decode_hand_frame(b"",0)

    def test_original_ps1_zero_palette_index_is_transparent(self):
        wa=bytearray(synthetic_wa())
        # Paleta da moldura de monstros: cor 0 da CLUT = transparente.
        struct.pack_into("<H",wa,assets.DUEL_CLUT_START+256*2,0)
        frame=assets.decode_hand_frame(bytes(wa),0)
        self.assertEqual(frame.getpixel((0,0))[3],0)
        self.assertEqual(frame.getpixel((2,0))[3],255)

    def test_large_and_small_art_exact_offsets_and_palette(self):
        wa=synthetic_wa()
        large,base=assets._large(wa,1)
        small,matching,offset=assets._small(wa,1)
        self.assertEqual(large.size,(102,96))
        self.assertEqual(small.size,(40,32))
        self.assertTrue(matching)
        self.assertEqual(base,722*2048)
        self.assertEqual(offset,0)
        corrupted=bytearray(wa)
        corrupted[722*2048+0x2AE0]^=1
        self.assertFalse(assets._small(bytes(corrupted),1)[1])

    def test_asset_pack_saves_original_and_framed_art_from_wa(self):
        wa=synthetic_wa()
        cards=[{"id":1,"type_id":0},{"id":2,"type_id":20}]
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(assets,"CARD_COUNT",2):
                report=assets.extract_asset_pack(
                    wa,cards,Path(temp),rom_sha256="c"*64)
            self.assertEqual(report["art_count"],2)
            self.assertEqual(report["thumbnail_count"],2)
            self.assertEqual(report["frame_count"],6)
            self.assertEqual(report["composed_count"],2)
            self.assertEqual(report["thumbnail_duplicate_matches"],2)
            self.assertEqual(report["status"],"completo")
            from PIL import Image
            with Image.open(Path(temp)/"cartas_com_moldura"/"001.png") as im:
                self.assertEqual(im.size,(52,60))
            self.assertTrue((Path(temp)/"artes_722"/"001.png").is_file())
            self.assertTrue((Path(temp)/"molduras_wa"/"1-magica.png").is_file())
            manifest=(Path(temp)/"recursos_wa.json").read_text("utf-8")
            self.assertIn('"thumbnail_matches_record": true',manifest)
            self.assertIn('"rom_sha256": "cccc',manifest)

    def test_mismatched_duplicate_does_not_invalidate_real_assets(self):
        wa=bytearray(synthetic_wa())
        # Mod pode alterar uma cópia da miniatura sem perder a arte original.
        base=assets.FIRST_CARD_SECTOR*assets.SECTOR+0x2AE0
        wa[base+3]^=1
        cards=[{"id":1,"type_id":0},{"id":2,"type_id":20}]
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(assets,"CARD_COUNT",2):
                result=assets.extract_asset_pack(
                    bytes(wa),cards,Path(temp),rom_sha256="a"*64)
            self.assertEqual(result["status"],"completo")
            self.assertEqual(result["thumbnail_duplicate_matches"],1)
            self.assertEqual(result["thumbnail_duplicate_mismatches"],1)
            self.assertEqual(result["composed_count"],2)

    def test_reject_non_hex_rom_signature(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(assets,"CARD_COUNT",2):
                with self.assertRaises(ValueError):
                    assets.extract_asset_pack(
                        synthetic_wa(),
                        [{"id":1,"type_id":0},{"id":2,"type_id":0}],
                        Path(temp),rom_sha256="x"*64)

    def test_reject_missing_or_repeated_card_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(assets,"CARD_COUNT",2):
                with self.assertRaises(ValueError):
                    assets.extract_asset_pack(synthetic_wa(),[{"id":1},{"id":1}],
                                              Path(temp),rom_sha256="x"*64)


if __name__=="__main__":
    unittest.main()
