"""Regressão sintética do decoder conhecido, sem nomes/dados de ROMs."""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scanner'))
from scanner_multiiso import (decode_names, inspect_known_name_layout,
    SLUS_PTR_BASE, SLUS_TEXT_BASE, SLUS_GLYPHS, SLUS_ATTRIBUTES)


def make_catalog(*, opponent_end=0xFF, header=False):
    sl=bytearray(SLUS_GLYPHS+93*4+100)
    for code,char in enumerate(('Ａ','Ｂ','Ｃ','ｖ'),1):
        struct.pack_into('<H',sl,SLUS_GLYPHS+code*4,
                         int.from_bytes(char.encode('shift_jis'),'big'))
    sl[SLUS_TEXT_BASE]=0xFF
    for i in range(1,723):
        ptr=1000+(i-1)*8
        struct.pack_into('<H',sl,SLUS_PTR_BASE+i*2,ptr)
        sl[SLUS_TEXT_BASE+ptr:SLUS_TEXT_BASE+ptr+4]=bytes([1,2,3,0xFF])
        packed=180+(150<<9)+(1<<18)+(2<<22)+(3<<26)
        struct.pack_into('<I',sl,SLUS_ATTRIBUTES+(i-1)*4,packed)
        sl[0x1C5B33+i-1]=0x24
    for i in range(1,40):
        ptr=9000+(i-1)*12
        struct.pack_into('<H',sl,SLUS_PTR_BASE+(0x328+i)*2,ptr)
        prefix=bytes([0xF8,0x0A,4]) if header else b''
        raw=prefix+bytes([1,2,3,4,opponent_end])
        sl[SLUS_TEXT_BASE+ptr:SLUS_TEXT_BASE+ptr+len(raw)]=raw
    return bytes(sl)


class KnownNameDecodingTests(unittest.TestCase):
    def test_canonical_ff_and_header_preserve_all_names_and_attributes(self):
        for header in (False,True):
            with self.subTest(header=header):
                opponents,cards,_=decode_names(make_catalog(header=header))
                self.assertEqual(len(opponents),39)
                self.assertEqual(len(cards),722)
                self.assertEqual(opponents[-1]['nome'],'ABCv')
                self.assertEqual(cards[-1],{'id':722,'nome':'ABC','atk':1800,
                    'def':1500,'tipo':3,'nivel':4,'atributo':2,
                    'estrela_1':1,'estrela_2':2})

    def test_unterminated_strings_cannot_borrow_ff_from_next_name(self):
        sl=bytearray(make_catalog())
        for i in range(38):
            start=SLUS_TEXT_BASE+9000+i*12
            sl[start:start+12]=bytes([1,2,3,4])*3
        opponents,cards,status=decode_names(bytes(sl))
        self.assertEqual(opponents,[])
        self.assertEqual(cards,[])
        self.assertIn('1/39',status)
        diagnostic=inspect_known_name_layout(bytes(sl))
        self.assertEqual(diagnostic['opponentSamples'][0]['recordStatus'],
                         'sem_ff_antes_proximo')

    def test_alternate_control_remains_unverified_without_suffix_cleanup(self):
        opponents,cards,_=decode_names(make_catalog(opponent_end=0xFE))
        self.assertEqual((opponents,cards),([],[]))
        diagnostic=inspect_known_name_layout(make_catalog(opponent_end=0xFE))
        row=diagnostic['opponentSamples'][0]
        self.assertEqual(row['name'],'ABCv')
        self.assertEqual(row['recordStatus'],'glifo_invalido')
        self.assertEqual(row['status'],'invalido_ou_vazio')

    def test_truncated_or_out_of_file_pointer_never_becomes_a_name(self):
        self.assertEqual(decode_names(bytes(20))[:2],([],[]))
        sl=bytearray(make_catalog())
        for i in range(1,40):
            struct.pack_into('<H',sl,SLUS_PTR_BASE+(0x328+i)*2,0xFFFF)
        self.assertEqual(decode_names(bytes(sl))[:2],([],[]))


if __name__=='__main__':
    unittest.main()
