"""Contrato permanente: nenhuma Preview sem versão e notas sincronizadas."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/security"))
sys.path.insert(0, str(ROOT / "scanner"))

import verify_preview_metadata as policy
from dueltrace_update_checker import CURRENT_VERSION


class PreviewReleaseMetadataPolicyTests(unittest.TestCase):
    def test_canonical_semver_branch_and_notes_are_consistent(self):
        self.assertEqual(policy.current_version(), CURRENT_VERSION)
        self.assertEqual(policy.verify_release_metadata(
            "feature/dueltrace-v0.12.0-card-details-hd-art"), CURRENT_VERSION)
        self.assertEqual(policy.verify_release_metadata("main"), CURRENT_VERSION)

    def test_old_branch_cannot_publish_newer_binary(self):
        with self.assertRaisesRegex(ValueError, "dessincronizados"):
            policy.verify_release_metadata(
                "feature/dueltrace-v097-old-preview")

    def test_missing_or_stale_patch_notes_block_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            note = Path(tmp) / "notes.md"
            with patch.object(policy, "NOTES", note):
                note.write_text("# DUELTRACE v0.9.7 — Preview\n"
                                "## Novidades\n- Antigo.\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "versão canônica"):
                    policy.verify_release_metadata()
                note.write_text(f"# DUELTRACE v{CURRENT_VERSION} — Preview\n"
                                "## Novidades\n- Atualização.\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "Novidades, Melhorias e Correções"):
                    policy.verify_release_metadata()

    def test_packaged_notes_are_displayable_without_network(self):
        from dueltrace_patch_notes import summarize_patch_notes
        raw = (ROOT / "docs/DUELTRACE_UPDATE_NOTES.md").read_text(
            encoding="utf-8")
        notes = summarize_patch_notes(raw)
        self.assertEqual([x["title"] for x in notes],
                         ["Novidades", "Melhorias", "Correções"])
        self.assertGreaterEqual(sum(len(x["items"]) for x in notes), 6)
        self.assertIn("BCD-POW", str(notes))


if __name__ == "__main__":
    unittest.main()
