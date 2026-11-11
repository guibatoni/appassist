"""Regression tests for updater visibility, private feed diagnostics and same-folder flow."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))
import dueltrace_web_bridge as bridge_mod
from dueltrace_private_update_source import PrivateUpdateUnavailable


class UpdateVisibilityV49Tests(unittest.TestCase):
    def base(self):
        return {
            "status":"unavailable","updateAvailable":False,
            "currentVersion":"0.9.7","channel":"preview",
            "previewError":None,"automaticInstallReason":"",
        }

    def instance(self):
        return bridge_mod.DueltraceWebBridge.__new__(
            bridge_mod.DueltraceWebBridge)

    def test_verified_new_private_preview_is_visible_and_displayed_by_build_id(self):
        release={
            "version":"0.9.7","run_id":42939025484,
            "sha":"a"*40,
            "page":"https://github.com/guibatoni/appassist/releases/tag/preview-v0.9.7-r42939025484",
            "patchNotes":[],
        }
        with (patch.object(bridge_mod,"check_for_updates",return_value=self.base()),
              patch.object(bridge_mod,"installed_preview_build_id",return_value=42935155350),
              patch.object(bridge_mod,"fetch_latest_preview_package",
                           return_value=release) as fetch):
            result=self.instance().check_updates()
        self.assertEqual(result["installedPreviewRunId"],42935155350)
        self.assertEqual(result["previewRunId"],42939025484)
        self.assertEqual(result["previewCheckStatus"],"checked")
        self.assertTrue(result["automaticPreviewReady"])
        self.assertTrue(result["updateAvailable"])
        fetch.assert_called_once_with(current_version="0.9.7",
                                      installed_run_id=42935155350)

    def test_checked_feed_without_new_release_is_not_authentication_failure(self):
        with (patch.object(bridge_mod,"check_for_updates",return_value=self.base()),
              patch.object(bridge_mod,"installed_preview_build_id",return_value=42939025484),
              patch.object(bridge_mod,"fetch_latest_preview_package",return_value=None)):
            result=self.instance().check_updates()
        self.assertEqual(result["previewCheckStatus"],"checked")
        self.assertFalse(result["automaticPreviewReady"])
        self.assertFalse(result["updateAvailable"])
        self.assertIsNone(result["previewError"])

    def test_missing_github_cli_is_displayed_and_never_claims_updated(self):
        error=PrivateUpdateUnavailable(
            "GitHub privado: instale o GitHub CLI e autorize a conta.")
        with (patch.object(bridge_mod,"check_for_updates",return_value=self.base()),
              patch.object(bridge_mod,"installed_preview_build_id",return_value=42935155350),
              patch.object(bridge_mod,"fetch_latest_preview_package",side_effect=error)):
            result=self.instance().check_updates()
        self.assertEqual(result["previewCheckStatus"],"authentication_required")
        self.assertIn("GitHub CLI",result["previewError"])
        self.assertFalse(result["automaticPreviewReady"])
        self.assertFalse(result["updateAvailable"])

    def test_update_dialog_is_portalled_above_scroll_not_hidden_by_shell(self):
        ui=(ROOT/"web/components/shell/update-checker.tsx").read_text(encoding="utf-8")
        bridge=(ROOT/"scanner/dueltrace_web_bridge.py").read_text(encoding="utf-8")
        checker=(ROOT/"scanner/dueltrace_update_checker.py").read_text(encoding="utf-8")
        self.assertIn('import { createPortal } from "react-dom"',ui)
        self.assertIn("createPortal(",ui)
        self.assertIn("document.body",ui)
        self.assertIn('aria-modal="true"',ui)
        self.assertIn('aria-label="Atualizar agora"',ui)
        self.assertIn("api.install_preview_update()",ui)
        self.assertIn("api.install_portable_update()",ui)
        self.assertIn("previewCheckStatus",ui)
        self.assertIn("installedPreviewRunId",ui)
        self.assertNotIn("api.open_updates_page(",ui)
        self.assertIn("nenhuma Preview mais recente",ui)
        self.assertIn('https://github.com/guibatoni/appassist/releases"',checker)
        self.assertIn('status["previewCheckStatus"]="checked"',bridge)


if __name__=="__main__":
    unittest.main()
