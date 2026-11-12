"""Avisos persistentes de atualização: identidade, offline e confirmação segura."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scanner"))

from dueltrace_update_checker import CURRENT_VERSION
from dueltrace_update_notice import (
    ACK_FILE, NOTES_FILE, read_installed_update_notice,
    acknowledge_installed_update_notice,
)


def make_bundle(home: Path, run_id: int = 43132392379, *,
                version: str = CURRENT_VERSION) -> Path:
    bundle = home / "packaged"
    bundle.mkdir(exist_ok=True)
    (bundle / "dueltrace-build.json").write_text(json.dumps({
        "schema": 1, "run_id": run_id, "version": version,
        "head_sha": "a" * 40,
    }), encoding="utf-8")
    (bundle / NOTES_FILE).write_text(
        f"# DUELTRACE v{version} — Preview\n\n"
        "## Novidades\n- Filtros agrupados de RANK.\n"
        "## Melhorias\n- Notas locais disponíveis.\n"
        "## Correções\n- Comparação segura do build.\n",
        encoding="utf-8",
    )
    return bundle


class InstalledUpdateNoticeTests(unittest.TestCase):
    def test_first_start_shows_notes_even_offline_then_only_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "user-data"
            bundle = make_bundle(Path(tmp))
            first = read_installed_update_notice(data, bundle=bundle)
            self.assertTrue(first["available"])
            self.assertTrue(first["unread"])
            self.assertEqual(first["version"], CURRENT_VERSION)
            self.assertEqual(len(first["notes"]), 3)
            self.assertFalse((data / ACK_FILE).exists())
            result = acknowledge_installed_update_notice(
                data, first["runId"], bundle=bundle)
            self.assertTrue(result["acknowledged"])
            self.assertFalse(read_installed_update_notice(data, bundle=bundle)["unread"])
            self.assertTrue((data / ACK_FILE).is_file())

    def test_new_build_reopens_news_even_when_version_number_is_same(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "user"
            bundle = make_bundle(Path(tmp), 43132392379)
            acknowledge_installed_update_notice(data, 43132392379, bundle=bundle)
            make_bundle(Path(tmp), 43132392380)
            latest = read_installed_update_notice(data, bundle=bundle)
            self.assertTrue(latest["unread"])
            self.assertEqual(latest["runId"], 43132392380)

    def test_invalid_or_old_identity_cannot_acknowledge_new_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "user"
            bundle = make_bundle(Path(tmp))
            for value in (0, -1, None, True, "43132392379", 43132392378):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    acknowledge_installed_update_notice(data, value, bundle=bundle)
            self.assertFalse((data / ACK_FILE).exists())

    def test_wrong_version_missing_notes_and_invalid_sha_suppress_notice(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            bundle = make_bundle(home, version="0.9.7")
            self.assertFalse(read_installed_update_notice(home, bundle=bundle)["available"])
            bundle = make_bundle(home)
            (bundle / NOTES_FILE).unlink()
            self.assertFalse(read_installed_update_notice(home, bundle=bundle)["available"])
            bundle = make_bundle(home)
            manifest = bundle / "dueltrace-build.json"
            data = json.loads(manifest.read_text())
            data["head_sha"] = "invalid"
            manifest.write_text(json.dumps(data), encoding="utf-8")
            self.assertFalse(read_installed_update_notice(home, bundle=bundle)["available"])


if __name__ == "__main__":
    unittest.main()
