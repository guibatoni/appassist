"""Commercial Lite activation gate, bridge security and isolation tests.

Private keys are generated in memory for TESTS ONLY; no real issuer key is used.
"""
from __future__ import annotations

import base64
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from dueltrace_offline_license import canonical_bytes, license_path, LicenseError
from dueltrace_commercial_runtime import CommercialLicenseGate
from dueltrace_web_security import ProtectedDesktopApi

TOKEN="test-token-"+"x"*38
DEVICE="c"*64


class FakeBridge:
    def __init__(self):
        self.calls=0

    def get_state(self):
        self.calls+=1
        return {"visible":"only after activation"}


class ActivationGateTests(unittest.TestCase):
    def setUp(self):
        self.homedir=tempfile.TemporaryDirectory()
        self.home=Path(self.homedir.name)
        self.private=Ed25519PrivateKey.generate()
        self.public=base64.b64encode(self.private.public_key().public_bytes(
            serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode()
        self.gate=CommercialLicenseGate(self.home,
                 device_fingerprint=lambda:DEVICE, public_key_b64=self.public)
        self.bridge=FakeBridge()
        self.api=ProtectedDesktopApi(self.bridge,TOKEN,license_gate=self.gate)

    def tearDown(self):
        self.homedir.cleanup()

    def signed(self,device_hash=DEVICE):
        payload={"schema":1,"product":"DUELTRACE","edition":"commercial-lite",
                 "license_id":str(uuid4()),"device_hash":device_hash,
                 "issued_on":"2026-01-01","expires_on":None}
        signature=self.private.sign(canonical_bytes(payload))
        return json.dumps({"payload":payload,
           "signature":base64.urlsafe_b64encode(signature).decode().rstrip("=")})

    def test_denies_all_business_api_before_activation(self):
        self.assertEqual(self.api.commercial_license_status(TOKEN)["status"],"not_activated")
        with self.assertRaises(PermissionError):
            self.api.get_state(TOKEN)
        self.assertEqual(self.bridge.calls,0)

    def test_request_never_exposes_machine_guid_and_requires_token(self):
        request=self.api.commercial_activation_request(TOKEN)
        data=json.loads(request["content"])
        self.assertEqual(data["device_hash"],DEVICE)
        self.assertNotIn("MachineGuid",request["content"])
        self.assertNotIn("ip",request["content"].lower())
        self.assertEqual(request["fileName"],"DUELTRACE-pedido-ativacao.json")
        with self.assertRaises(PermissionError):
            self.api.commercial_activation_request("bad")
        with self.assertRaises(PermissionError):
            self.api.commercial_license_status("bad")

    def test_activation_unlocks_all_protected_calls_and_persists(self):
        result=self.api.commercial_activate_license(TOKEN,self.signed())
        self.assertTrue(result["active"])
        self.assertEqual(self.api.commercial_license_status(TOKEN)["status"],"active")
        self.assertEqual(self.api.get_state(TOKEN),{"visible":"only after activation"})
        self.assertEqual(self.bridge.calls,1)
        self.assertTrue(license_path(self.home).exists())
        self.assertEqual(CommercialLicenseGate(self.home,
            device_fingerprint=lambda:DEVICE,public_key_b64=self.public).status()["status"],"active")

    def test_rejects_wrong_hardware_modified_license_and_excessive_size(self):
        with self.assertRaises(LicenseError):
            self.api.commercial_activate_license(TOKEN,self.signed("d"*64))
        with self.assertRaises(LicenseError):
            self.api.commercial_activate_license(TOKEN,"{"+" "*10000+"}")
        doc=json.loads(self.signed())
        doc["payload"]["device_hash"]="d"*64
        with self.assertRaises(LicenseError):
            self.api.commercial_activate_license(TOKEN,json.dumps(doc))
        self.assertFalse(license_path(self.home).exists())
        self.assertEqual(self.bridge.calls,0)

    def test_missing_file_after_activation_relocks_python_api(self):
        self.api.commercial_activate_license(TOKEN,self.signed())
        license_path(self.home).unlink()
        with self.assertRaises(PermissionError):
            self.api.get_state(TOKEN)

    def test_alpha_has_no_license_requirements(self):
        api=ProtectedDesktopApi(self.bridge,TOKEN)
        self.assertEqual(api.commercial_license_status(TOKEN),
                         {"edition":"alpha","active":True,"status":"not_required"})
        self.assertEqual(api.get_state(TOKEN),{"visible":"only after activation"})
        with self.assertRaises(PermissionError):
            api.commercial_activation_request(TOKEN)
        with self.assertRaises(PermissionError):
            api.commercial_activate_license(TOKEN,self.signed())

    def test_commercial_alpha_update_channels_are_blocked(self):
        self.api.commercial_activate_license(TOKEN,self.signed())
        for action in (
            self.api.check_updates, self.api.install_preview_update,
            self.api.install_portable_update, self.api.install_signed_update,
            self.api.open_updates_page,
        ):
            with self.subTest(action=action.__name__),self.assertRaises(PermissionError):
                action(TOKEN)

    def test_file_reader_rejects_symlink(self):
        data=self.signed()
        other=self.home/"other.json"
        other.write_text(data,encoding="utf-8")
        license=license_path(self.home)
        license.parent.mkdir(parents=True,exist_ok=True)
        try:
            license.symlink_to(other)
        except (OSError,NotImplementedError):
            self.skipTest("Symlink creation requires Windows Developer Mode")
        self.assertFalse(self.gate.status()["active"])


class CommercialWiringTests(unittest.TestCase):
    def test_executables_are_isolated_and_api_guard_is_on_python_side(self):
        desktop=(ROOT/"scanner/dueltrace_web_desktop.py").read_text(encoding="utf-8")
        entry=(ROOT/"scanner/dueltrace_commercial_entry.py").read_text(encoding="utf-8")
        protected=(ROOT/"scanner/dueltrace_web_security.py").read_text(encoding="utf-8")
        script=(ROOT/".github/workflows/validar-webui-desktop.yml").read_text(encoding="utf-8")
        self.assertIn("main(commercial=True)",entry)
        self.assertIn("def main(*, commercial: bool = False):",desktop)
        self.assertIn("license_gate.require_active()",desktop)
        self.assertIn("self._license_gate.require_active()",protected)
        self.assertIn("scanner/dueltrace_commercial_entry.py",script)
        self.assertIn("--name DUELTRACE-Commercial",script)
        self.assertIn("scanner/dueltrace_web_desktop.py",script)
        self.assertIn("commercial/dueltrace-lite-activation-v40",str(
            ROOT.joinpath("scanner/dueltrace_commercial_entry.py")))
        # The runtime must not have a production key at this stage.
        self.assertIn('PUBLIC_KEY_B64 = ""',(
            ROOT/"scanner/dueltrace_commercial_public_key.py").read_text(encoding="utf-8"))

    def test_ui_routes_to_guard_without_remote_licensing(self):
        app=(ROOT/"web/components/shell/app-shell.tsx").read_text(encoding="utf-8")
        dialog=(ROOT/"web/components/shell/commercial-activation.tsx").read_text(encoding="utf-8")
        updater=(ROOT/"web/components/shell/top-bar.tsx").read_text(encoding="utf-8")
        self.assertIn("<CommercialActivationGuard>",app)
        self.assertIn("commercial_activate_license(raw)",dialog)
        self.assertIn("commercial_activation_request()",dialog)
        self.assertIn("backdrop-blur-lg",dialog)
        self.assertIn("Salvar pedido",dialog)
        self.assertIn("showAlphaUpdates",updater)
        self.assertNotIn("fetch(",dialog)


if __name__=="__main__":
    unittest.main()
