"""Regressão: nomes complexos de ROM e reconciliação da pasta de extração."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from importador_perfis import import_rom
from scanner_multiiso import process


class FakeDisc:
    def __init__(self, path):
        self.sector=2352
        self.files={
            "SLUS_014.11":(20,3_000_000),
            "WA_MRG.MRG":(800,20_000_000),
        }
    def get(self,name,limit_bytes=None):
        if name=="SLUS_014.11":return b"S"*256
        return b"W"*128
    def close(self):pass


class FolderContractTests(unittest.TestCase):
    def test_import_exact_path_for_complex_rom_filenames(self):
        names=[
            "Yu-Gi-Oh! Remaster [VER. 1.2.1 - X15 - NO REQUIREMENTS].bin",
            "Yu-Gi-Oh! FM Original (Drop x15).bin",
            "Novo Mod - Edição [β] (v2).iso",
            "FM..-- [ Edição! ] 13.iso",
        ]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with (patch("scanner_multiiso.Disc",FakeDisc),
                  patch("scanner_multiiso.decode_names",return_value=([],[],"não decodificado")),
                  patch("scanner_multiiso.decode_drops",return_value=(None,"desconhecido"))):
                for name in names:
                    rom=root/name
                    rom.write_bytes(b"\x00"*128000)
                    expected=hashlib.sha256(rom.read_bytes()).hexdigest()
                    profile,profile_file=import_rom(rom,root/"dados")
                    self.assertTrue(profile_file.is_file(),name)
                    self.assertEqual(profile["rom_sha256"],expected)
                    extracted=Path(profile["scan_result_dir"])
                    self.assertTrue(extracted.is_dir(),name)
                    report=json.loads((extracted/"relatorio.json").read_text(encoding="utf-8"))
                    self.assertEqual(report["arquivo"],name)
                    self.assertEqual(Path(report["resultado_dir"]),extracted)
                    self.assertFalse(profile["supported_features"]["cards"])

    def test_old_csv_not_reused_after_failed_scan(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            rom=root/"Mod [pasta] - 13.iso"
            rom.write_bytes(b"x"*128000)
            output=root/"analysis"
            with (patch("scanner_multiiso.Disc",FakeDisc),
                  patch("scanner_multiiso.decode_names",return_value=([],[],"sem dados")),
                  patch("scanner_multiiso.decode_drops",return_value=(None,"sem tabelas"))):
                result=process(rom,output)
                stale=Path(result["resultado_dir"])/"cartas.csv"
                stale.write_text("id,nome\\n1,ERRADO",encoding="utf-8")
                result2=process(rom,output,digest=result["sha256"])
                self.assertFalse(stale.exists())
                self.assertEqual(result2["status"],"incerto: estrutura não reconhecida; sem atribuições automáticas")

    def test_import_must_not_accept_outside_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            rom=root/"mod.iso"
            rom.write_bytes(b"x"*128000)
            outside=root/"other"
            outside.mkdir()
            # Código de terceiros não deve induzir o importador a ler caminho externo.
            fake={"resultado_dir":str(outside),"status":"incerto"}
            with patch("importador_perfis.process",return_value=fake):
                with self.assertRaisesRegex(RuntimeError,"fora do diretório"):
                    import_rom(rom,root/"output")


if __name__=="__main__":
    unittest.main()
