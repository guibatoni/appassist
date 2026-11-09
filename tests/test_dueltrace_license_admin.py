"""Batoni Dev offline administrator: issuance, recovery, storage and UI contracts.

All keys are generated ephemerally inside TemporaryDirectory. NEVER use
production credentials, customer data or example signing keys in CI.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scanner"))
sys.path.insert(0, str(ROOT / "tools" / "licensing"))

from cryptography.hazmat.primitives import serialization

from dueltrace_offline_license import LicenseError, activation_request, verify_license
from dueltrace_license_admin_core import (
    MAX_DEVICES_PER_ORDER, admin_paths, check_password, create_keys, export_public_key,
    has_keys, issue_license, list_issued, normalize_order_ref, read_request,
    read_request_file, recover_public_key, resend_issued, verify_issued,
    _public_b64,
)

PASSWORD = "Admin-Test-Long-Strong-Password-2026"
ORDER = "PATREON-0001"


class LicenseManagerCoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "owner"
        self.output = Path(self.temp.name) / "output"
        self.output.mkdir()
        self.public = create_keys(self.home, PASSWORD, PASSWORD)

    def request(self, character: str):
        return activation_request(character * 64)

    def emit(self, character: str, name: str, *, order: str = ORDER,
             request: dict | None = None, password: str = PASSWORD,
             confirmed: bool = True, expires: str | None = None):
        req = request if request is not None else self.request(character)
        dest = self.output / (name + ".json")
        result = issue_license(
            self.home, password, req, order, dest,
            purchase_confirmed=confirmed, expires_on=expires)
        return result, dest, req

    def test_encrypted_private_key_and_public_export(self):
        paths = admin_paths(self.home)
        private = paths["private"].read_bytes()
        self.assertIn(b"ENCRYPTED PRIVATE KEY", private)
        self.assertNotIn(PASSWORD.encode(), private)
        self.assertTrue(has_keys(self.home))
        self.assertEqual(len(self.public), 44)
        self.assertEqual(_public_b64(self.home), self.public)
        self.assertTrue(check_password(self.home, PASSWORD))
        with self.assertRaises(LicenseError):
            check_password(self.home, "incorrect")
        with self.assertRaises(LicenseError):
            create_keys(self.home, PASSWORD, PASSWORD)
        public_export = self.output / "public.txt"
        export_public_key(self.home, public_export)
        self.assertEqual(public_export.read_text().strip(), self.public)
        with self.assertRaises(LicenseError):
            export_public_key(self.home, public_export)

    def test_broken_key_pair_is_not_used_for_issuance(self):
        other = Path(self.temp.name) / "other"
        create_keys(other, PASSWORD, PASSWORD)
        admin_paths(self.home)["public"].write_bytes(
            admin_paths(other)["public"].read_bytes())
        with self.assertRaises(LicenseError):
            self.emit("a", "wrong-public-key")
        self.assertEqual(list_issued(self.home), [])

    def test_recover_only_missing_public_using_private_password(self):
        path = admin_paths(self.home)["public"]
        path.unlink()
        with self.assertRaises(LicenseError):
            recover_public_key(self.home, "wrong")
        self.assertEqual(recover_public_key(self.home, PASSWORD), self.public)
        with self.assertRaises(LicenseError):
            recover_public_key(self.home, PASSWORD)

    def test_issue_valid_perpetual_license_and_backup(self):
        result, dest, req = self.emit("a", "first")
        data = json.loads(dest.read_text(encoding="utf-8"))
        verified = verify_license(data, req["device_hash"],
                                  public_key_b64=self.public)
        self.assertTrue(verified["active"])
        self.assertIsNone(verified["expiresOn"])
        self.assertEqual(result["license_id"], verified["licenseId"])
        self.assertEqual(verify_issued(self.home, dest)["licenseId"],
                         result["license_id"])
        source = admin_paths(self.home)["issued"] / (result["license_id"] + ".json")
        self.assertEqual(source.read_bytes(), dest.read_bytes())
        record = list_issued(self.home)[0]
        self.assertEqual(record["order_ref"], ORDER)
        self.assertEqual(record["request_id"], req["request_id"])
        self.assertNotIn("email", record)

    def test_duplicate_request_device_and_third_device_rejected(self):
        first, _, request = self.emit("a", "one")
        with self.assertRaises(LicenseError):
            self.emit("a", "duplicate-request", request=request)
        with self.assertRaises(LicenseError):
            self.emit("a", "duplicate-device")
        self.emit("b", "two")
        with self.assertRaisesRegex(LicenseError, "dois"):
            self.emit("c", "three")
        self.assertEqual(len(list_issued(self.home)), MAX_DEVICES_PER_ORDER)
        self.assertFalse((self.output / "three.json").exists())

    def test_another_order_can_activate_new_device(self):
        self.emit("a", "one")
        self.emit("b", "two", order="PATREON-0002")
        self.assertEqual(len(list_issued(self.home)), 2)

    def test_payment_and_password_must_be_valid(self):
        with self.assertRaisesRegex(LicenseError, "pagamento"):
            self.emit("a", "unpaid", confirmed=False)
        with self.assertRaises(LicenseError):
            self.emit("a", "wrong-pw", password="bad")
        self.assertEqual(list_issued(self.home), [])

    def test_expiry_and_format_validation(self):
        with self.assertRaises(LicenseError):
            self.emit("a", "past", expires="2020-01-01")
        with self.assertRaises(LicenseError):
            self.emit("a", "invalid", expires="2026-02-30")
        future = (date.today() + timedelta(days=30)).isoformat()
        result, path, _ = self.emit("a", "future", expires=future)
        self.assertEqual(verify_issued(self.home, path)["expiresOn"], future)
        self.assertEqual(result["order_ref"], ORDER)

    def test_request_validation_and_output_nondestructive(self):
        req = self.request("a")
        self.assertEqual(read_request(json.dumps(req))["request_id"], req["request_id"])
        malformed = {**req, "device_hash": "wrong"}
        with self.assertRaises(LicenseError):
            read_request(json.dumps(malformed))
        malformed = {**req, "password": "intrusion"}
        with self.assertRaises(LicenseError):
            read_request(json.dumps(malformed))
        with self.assertRaises(LicenseError):
            read_request(b" " * 8193)
        invalid = self.output / "request.json"
        invalid.write_bytes(b"x" * 9000)
        with self.assertRaises(LicenseError):
            read_request_file(invalid)
        existing = self.output / "existing.json"
        existing.write_text("preserve", encoding="utf-8")
        with self.assertRaises(LicenseError):
            issue_license(self.home, PASSWORD, req, ORDER, existing,
                          purchase_confirmed=True)
        self.assertEqual(existing.read_text(), "preserve")
        self.assertFalse(admin_paths(self.home)["ledger"].exists())

    def test_resend_original_license_without_new_activation(self):
        result, first, _ = self.emit("a", "original")
        backup = self.output / "resend.json"
        status = resend_issued(self.home, result["license_id"], backup)
        self.assertEqual(status["licenseId"], result["license_id"])
        self.assertEqual(first.read_bytes(), backup.read_bytes())
        self.assertEqual(len(list_issued(self.home)), 1)
        with self.assertRaises(LicenseError):
            resend_issued(self.home, result["license_id"], backup)

    def test_corrupted_ledger_fails_closed(self):
        admin_paths(self.home)["ledger"].write_text("{invalid", encoding="utf-8")
        with self.assertRaises(LicenseError):
            self.emit("a", "no-issue")
        self.assertFalse((self.output / "no-issue.json").exists())

    def test_lock_is_removed_and_duplicate_lock_refused(self):
        self.emit("a", "one")
        lock = admin_paths(self.home)["lock"]
        self.assertFalse(lock.exists())
        lock.write_text("locked", encoding="utf-8")
        with self.assertRaises(LicenseError):
            self.emit("b", "blocked")
        self.assertEqual(lock.read_text(), "locked")
        self.assertFalse((self.output / "blocked.json").exists())

    def test_order_reference_is_strict(self):
        self.assertEqual(normalize_order_ref("  patreon-0001 "), ORDER)
        for bad in ("", "x", "../bad", " cliente@email.com ", "X" * 70):
            with self.subTest(bad=bad), self.assertRaises(LicenseError):
                normalize_order_ref(bad)

    def test_private_key_is_never_in_signed_license_or_ledger(self):
        result, path, _ = self.emit("a", "first")
        private_bytes = admin_paths(self.home)["private"].read_bytes()
        all_export = path.read_bytes() + admin_paths(self.home)["ledger"].read_bytes()
        self.assertNotIn(b"ENCRYPTED PRIVATE KEY", all_export)
        self.assertNotIn(private_bytes, all_export)
        self.assertNotIn(PASSWORD.encode(), all_export)
        self.assertIn(result["license_id"].encode(), all_export)


class LicenseAdminPackageTests(unittest.TestCase):
    def test_admin_isolated_from_customer_app(self):
        gui = (ROOT / "tools/licensing/dueltrace_license_admin.py").read_text(encoding="utf-8")
        core = (ROOT / "tools/licensing/dueltrace_license_admin_core.py").read_text(encoding="utf-8")
        entry = (ROOT / "scanner/dueltrace_commercial_entry.py").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/validar-licencas-admin-windows.yml").read_text(encoding="utf-8")
        self.assertIn("tkinter", gui)
        self.assertIn("Gerenciador de Licenças", gui)
        self.assertIn("emit_license", gui)
        self.assertIn("resend_license", gui)
        self.assertIn("create_keys", core)
        self.assertNotIn("dueltrace_license_admin", entry)
        self.assertIn("BatoniDev-LicenseManager", workflow)
        self.assertIn("actions/upload-artifact@v4", workflow)
        self.assertNotIn("private_key.pem", workflow)
        self.assertNotIn("issuer_ed25519_private.pem", workflow)

    def test_admin_key_location_outside_repository(self):
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": r"C:\Users\Test\AppData\Local"}):
            with mock.patch("dueltrace_license_admin_core.os.name", "nt"):
                from dueltrace_license_admin_core import default_admin_home
                path = str(default_admin_home())
                self.assertIn("BatoniDev", path)
                self.assertNotIn("GitHub", path)


if __name__ == "__main__":
    unittest.main()
