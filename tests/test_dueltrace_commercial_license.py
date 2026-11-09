"""Commercial Lite: offline Ed25519 contracts (no real customer secrets)."""
import base64
import copy
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from uuid import uuid4

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from dueltrace_offline_license import (
    LicenseError, PRODUCT, EDITION, canonical_bytes, activation_request,
    verify_license, install_license, local_license_status, license_path,
)


class OfflineLicenseTests(unittest.TestCase):
    def setUp(self):
        self.device="a"*64
        self.other="b"*64
        self.private=Ed25519PrivateKey.generate()
        self.public=base64.b64encode(
            self.private.public_key().public_bytes(
                serialization.Encoding.Raw,serialization.PublicFormat.Raw)
            ).decode("ascii")
        self.payload={
            "schema":1,"product":PRODUCT,"edition":EDITION,
            "license_id":str(uuid4()),"device_hash":self.device,
            "issued_on":"2026-01-01","expires_on":None,
        }

    def signed(self,payload=None):
        payload=copy.deepcopy(self.payload if payload is None else payload)
        signature=self.private.sign(canonical_bytes(payload))
        return {"payload":payload,
                "signature":base64.urlsafe_b64encode(signature).decode().rstrip("=")}

    def verify(self,doc=None,device=None,day=date(2026,11,9)):
        return verify_license(doc if doc is not None else self.signed(),
                              device or self.device,public_key_b64=self.public,today=day)

    def test_valid_perpetual_signature(self):
        status=self.verify()
        self.assertTrue(status["active"])
        self.assertIsNone(status["expiresOn"])
        self.assertEqual(status["licenseId"],self.payload["license_id"])

    def test_never_uses_ip_in_activation_request(self):
        request=activation_request(self.device)
        self.assertEqual(request["device_hash"],self.device)
        self.assertEqual(set(request),{"schema","product","edition","request_id","device_hash"})
        self.assertNotIn("ip",str(request).lower())

    def test_rejects_tampering_and_wrong_hardware(self):
        doc=self.signed()
        doc["payload"]["device_hash"]=self.other
        with self.assertRaises(LicenseError):
            self.verify(doc)
        with self.assertRaises(LicenseError):
            self.verify(self.signed(),self.other)

    def test_rejects_signature_and_unknown_fields(self):
        doc=self.signed()
        doc["signature"]="A"*86
        with self.assertRaises(LicenseError):
            self.verify(doc)
        doc=self.signed()
        doc["payload"]["ip"]="127.0.0.1"
        with self.assertRaises(LicenseError):
            self.verify(doc)

    def test_rejects_expired_future_and_invalid_dates(self):
        expired={**self.payload,"expires_on":"2026-06-01"}
        with self.assertRaises(LicenseError):
            self.verify(self.signed(expired))
        future={**self.payload,"issued_on":"2030-01-01"}
        with self.assertRaises(LicenseError):
            self.verify(self.signed(future))
        invalid={**self.payload,"expires_on":"2026-02-30"}
        with self.assertRaises(LicenseError):
            self.verify(self.signed(invalid))

    def test_fails_closed_without_public_key(self):
        with self.assertRaisesRegex(LicenseError,"pública"):
            verify_license(self.signed(),self.device,public_key_b64="")

    def test_install_is_validated_and_kept_outside_app_files(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            self.assertFalse(local_license_status(home,device_hash=self.device,
                                                   public_key_b64=self.public)["active"])
            result=install_license(self.signed(),home,self.device,
                                   public_key_b64=self.public)
            self.assertTrue(result["active"])
            path=license_path(home)
            self.assertEqual(path.parent,home/"commercial")
            self.assertTrue(path.exists())
            self.assertEqual(
                local_license_status(home,device_hash=self.device,
                                     public_key_b64=self.public)["status"],"active")
            with self.assertRaises(LicenseError):
                install_license(self.signed(),home,self.other,public_key_b64=self.public)

    def test_excessively_large_license_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            path=license_path(root)
            path.parent.mkdir(parents=True)
            path.write_bytes(b" " * 8193)
            status=local_license_status(root,device_hash=self.device,
                                        public_key_b64=self.public)
            self.assertEqual(status["status"],"invalid")


class CommercialInstallerTests(unittest.TestCase):
    def test_installer_is_per_user_preserves_appdata_and_not_published(self):
        root=Path(__file__).resolve().parents[1]
        nsis=(root/"installer/dueltrace-commercial-lite.nsi").read_text(encoding="utf-8")
        workflow=(root/".github/workflows/validar-webui-desktop.yml").read_text(encoding="utf-8")
        public=(root/"scanner/dueltrace_commercial_public_key.py").read_text(encoding="utf-8")
        self.assertIn("RequestExecutionLevel user",nsis)
        self.assertIn('InstallDirRegKey HKCU',nsis)
        self.assertIn('InstallLocation',nsis)
        self.assertIn('OutFile "DUELTRACE-Setup-TESTE.exe"',nsis)
        self.assertIn('RMDir /r "$INSTDIR\\_internal"',nsis)
        self.assertNotIn("RMDir /r $LOCALAPPDATA",nsis)
        self.assertNotIn("tools/licensing/dueltrace_license_cli.py",workflow)
        self.assertIn('PUBLIC_KEY_B64 = ""',public)
        self.assertIn("cryptography==50.0.2",workflow)
        self.assertIn("cryptography==50.0.2",(
            root/"tools/security/requirements-webui-build.txt").read_text(encoding="utf-8"))


if __name__=="__main__":
    unittest.main()
