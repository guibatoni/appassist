"""Regressão da inspeção de pacotes Windows: não executa binários."""
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "security"))
from audit_windows_archive import audit_zip


class ArchiveSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / "build"
        self.folder.mkdir()
        (self.folder / "DUELTRACE-WebUI.exe").write_bytes(b"MZ" + b"a" * 128)
        (self.folder / "_internal").mkdir()
        (self.folder / "_internal" / "library.dll").write_bytes(b"good data")
        self.archive = self.root / "app.zip"

    def pack(self, replacement=None, extra=None):
        replacement = replacement or {}
        with zipfile.ZipFile(self.archive, "w", zipfile.ZIP_DEFLATED) as z:
            for p in self.folder.rglob("*"):
                if p.is_file():
                    rel = p.relative_to(self.folder).as_posix()
                    z.writestr(rel, replacement.get(rel, p.read_bytes()))
            for key, value in (extra or {}).items():
                z.writestr(key, value)

    def test_matching_archive_is_accepted(self):
        self.pack()
        report = audit_zip(self.folder, self.archive)
        self.assertEqual(report["files_verified"], 2)
        self.assertFalse(report["authenticode_signature_verified"])

    def test_same_size_mutated_binary_is_detected(self):
        self.pack(replacement={"DUELTRACE-WebUI.exe": b"MZ" + b"b" * 128})
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            audit_zip(self.folder, self.archive)

    def test_traversal_and_unexamined_entry_are_rejected(self):
        for name in ("../injected.exe", "/root.exe", "_internal/foreign.exe"):
            with self.subTest(name=name):
                self.pack(extra={name: b"evil"})
                with self.assertRaises(ValueError):
                    audit_zip(self.folder, self.archive)

    def test_private_rom_and_secrets_rejected(self):
        for name in ("DATA/WA_MRG.MRG", "DATA/SLUS_014.11",
                     "rom.iso", "backup.mcr", "secret.pfx"):
            with self.subTest(name=name):
                self.pack(extra={name: b"private"})
                with self.assertRaises(ValueError):
                    audit_zip(self.folder, self.archive)

    def test_missing_file_from_zip_rejected(self):
        with zipfile.ZipFile(self.archive, "w") as z:
            z.write(self.folder / "DUELTRACE-WebUI.exe", "DUELTRACE-WebUI.exe")
        with self.assertRaisesRegex(ValueError, "não inclui"):
            audit_zip(self.folder, self.archive)

    def test_duplicate_entry_rejected(self):
        self.pack()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.archive, "a") as z:
                z.write(self.folder / "DUELTRACE-WebUI.exe", "DUELTRACE-WebUI.exe")
        with self.assertRaisesRegex(ValueError, "duplicada"):
            audit_zip(self.folder, self.archive)


if __name__ == "__main__":
    unittest.main()
