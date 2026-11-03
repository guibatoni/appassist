"""Testes unitários de sanidade da auditoria profunda."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scanner"))
from deep_asset_audit import TARGETS, audit_image, read_target


class FakeDisc:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.files = {TARGETS[0]: (12, len(payload))}

    def read(self, lba: int, size: int) -> bytes:
        offset = (lba - 12) * 2048
        return self.payload[offset:offset + size]


class AuditTests(unittest.TestCase):
    def test_missing_target(self):
        data, report = read_target(FakeDisc(b"abc"), TARGETS[1])
        self.assertEqual(data, b"")
        self.assertEqual(report["status"], "ausente")

    def test_full_file_and_digest(self):
        import hashlib
        payload = bytes(range(256)) * 20000 + b"tail"
        data, report = read_target(FakeDisc(payload), TARGETS[0])
        self.assertEqual(data, payload)
        self.assertEqual(report["bytes_read"], len(payload))
        self.assertEqual(report["sha256"], hashlib.sha256(payload).hexdigest())

    def test_size_limit(self):
        disc = FakeDisc(b"")
        disc.files[TARGETS[0]] = (12, 257 * 1024 * 1024)
        data, report = read_target(disc, TARGETS[0])
        self.assertEqual(data, b"")
        self.assertEqual(report["status"], "limite_excedido")


if __name__ == "__main__":
    unittest.main()
