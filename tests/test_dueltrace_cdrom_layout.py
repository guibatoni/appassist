"""Testes ISO9660 sintéticos para .iso e .bin com diferentes geometrias.

Nenhuma ROM comercial é usada. O parser deve provar a geometria pelo PVD,
ler arquivos sem truncamento e rejeitar ciclos e extents fora do disco.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))

from scanner_multiiso import Disc, SCAN_PARSER_REVISION
from dueltrace_cdrom_layout import detect_disc_geometry, SUPPORTED_LAYOUTS


def record(name: bytes, lba: int, size: int, *, directory: bool=False) -> bytes:
    length=33+len(name)+(1 if len(name)%2==0 else 0)
    buf=bytearray(length)
    buf[0]=length
    buf[2:6]=lba.to_bytes(4,"little")
    buf[6:10]=lba.to_bytes(4,"big")
    buf[10:14]=size.to_bytes(4,"little")
    buf[14:18]=size.to_bytes(4,"big")
    buf[25]=2 if directory else 0
    buf[28:30]=(1).to_bytes(2,"little")
    buf[30:32]=(1).to_bytes(2,"big")
    buf[32]=len(name)
    buf[33:33+len(name)]=name
    return bytes(buf)


def synthetic_image(sector: int, offset: int, *, cycle=False,
                    oversized_dir=False, invalid_file_extent=False,
                    corrupt_magic=False) -> bytes:
    data=[bytearray(2048) for _ in range(32)]
    pvd=data[16]
    pvd[:7]=b"\x01CD001\x01" if not corrupt_magic else b"\x01BROKE\x01"
    root_size=(9*1024*1024 if oversized_dir else 2048)
    root=record(b"\x00",20,root_size,directory=True)
    pvd[156:156+len(root)]=root
    entries=[
        record(b"\x00",20,2048,directory=True),
        record(b"\x01",20,2048,directory=True),
        record(b"TEST.DAT;1",10000 if invalid_file_extent else 21,11),
    ]
    if cycle:
        entries.append(record(b"LOOP",20,2048,directory=True))
    data[20][:sum(map(len,entries))]=b"".join(entries)
    data[21][:11]=b"hello world"
    if sector==2048:
        return b"".join(data)
    return b"".join(
        (b"\x00"*offset+bytes(x)+b"\x00"*(sector-offset-2048))
        for x in data
    )


class DiscGeometryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def path_for(self,data: bytes,suffix: str = ".bin") -> Path:
        p=Path(self.tmp.name)/("sample"+suffix)
        p.write_bytes(data)
        return p

    def test_all_supported_geometries_with_renamed_executable_and_resources(self):
        for sector,offset,label in SUPPORTED_LAYOUTS:
            with self.subTest(label=label):
                p=self.path_for(synthetic_image(sector,offset),".iso")
                disk=Disc(p)
                try:
                    self.assertEqual((disk.sector,disk.offset,disk.geometry),
                                     (sector,offset,label))
                    self.assertEqual(disk.get("test.dat"),b"hello world")
                    self.assertEqual(disk.files["TEST.DAT"],(21,11))
                finally:
                    disk.close()

    def test_extension_does_not_determine_physical_geometry(self):
        for suffix in (".bin",".iso"):
            with self.subTest(suffix=suffix):
                p=self.path_for(synthetic_image(2352,24),suffix)
                with Disc(p).f as stream:
                    result=detect_disc_geometry(stream,p.stat().st_size)
                    self.assertEqual(result.sector,2352)
                    self.assertEqual(result.offset,24)

    def test_read_does_not_escape_end_of_disc_or_file(self):
        p=self.path_for(synthetic_image(2336,8))
        disc=Disc(p)
        try:
            with self.assertRaises(ValueError):
                disc.read(31,4096)
            with self.assertRaises(ValueError):
                disc.read(-1,2048)
            self.assertEqual(disc.get("test.dat",limit_bytes=5),b"hello")
        finally:
            disc.close()

    def test_invalid_magic_and_tiny_images_fail_closed(self):
        for image in (b"bad",synthetic_image(2352,24,corrupt_magic=True)):
            with self.subTest(size=len(image)):
                p=self.path_for(image)
                with self.assertRaises(ValueError):
                    Disc(p)

    def test_rejects_cyclic_directory_without_recursing(self):
        p=self.path_for(synthetic_image(2048,0,cycle=True))
        with self.assertRaisesRegex(ValueError,"cíclico"):
            Disc(p)

    def test_rejects_oversized_directory_before_reading(self):
        p=self.path_for(synthetic_image(2048,0,oversized_dir=True))
        with self.assertRaisesRegex(ValueError,"tamanho inválido"):
            Disc(p)

    def test_rejects_extent_outside_disk(self):
        p=self.path_for(synthetic_image(2352,24,invalid_file_extent=True))
        with self.assertRaisesRegex(ValueError,"além do limite"):
            Disc(p)

    def test_scanner_revision_records_format_change_for_cache(self):
        self.assertGreaterEqual(SCAN_PARSER_REVISION,8)


if __name__=="__main__":
    unittest.main()
