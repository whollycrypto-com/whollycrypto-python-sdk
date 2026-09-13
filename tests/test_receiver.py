import hashlib
import hmac
import importlib.util
import io
import json
import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from tests.helpers import ASSET, INVOICE, PROJECT, STORE

spec = importlib.util.spec_from_file_location(
    "receiver", Path(__file__).resolve().parents[1] / "examples/webhook_wsgi.py"
)
receiver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(receiver)
SECRET = "only-a-receiver-test-secret"


class ReceiverTests(unittest.TestCase):
    @staticmethod
    def deliver(app, raw, event=PROJECT, valid=True, method="POST"):
        stamp = str(int(time.time()))
        signature = (
            "t="
            + stamp
            + ",v1="
            + hmac.new(SECRET.encode(), stamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
        )
        environ = {
            "REQUEST_METHOD": method,
            "CONTENT_LENGTH": str(len(raw)),
            "wsgi.input": io.BytesIO(raw),
            "HTTP_WHOLLY_SIGNATURE": signature if valid else "invalid",
            "HTTP_WHOLLY_EVENT_ID": event,
            "HTTP_WHOLLY_DELIVERY_ID": STORE,
        }
        result = []
        body = b"".join(app(environ, lambda status, headers: result.append((status, headers))))
        assert body == b""
        return int(result[0][0].split()[0])

    def test_authenticate_before_storage_durable_replay_protection(self):
        with tempfile.TemporaryDirectory(prefix="wholly-python-receiver-") as folder:
            path = Path(folder) / "inbox.sqlite"
            app = receiver.create_app(SECRET, path, PROJECT)
            raw = json.dumps({"invoice_id": INVOICE, "sequence": 3, "status": "settled"}).encode()
            self.assertEqual(400, self.deliver(app, raw, valid=False))
            self.assertFalse(path.exists())
            self.assertEqual(204, self.deliver(app, raw))
            self.assertEqual(204, self.deliver(app, raw))
            self.assertEqual(
                204, self.deliver(app, raw, event=ASSET)
            )  # Unsigned ID cannot bypass deduplication.
            with sqlite3.connect(path) as connection:
                self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM wholly_inbox").fetchone()[0])
                self.assertEqual(raw, connection.execute("SELECT payload FROM wholly_inbox").fetchone()[0])
            self.assertEqual(0o600, path.stat().st_mode & 0o777)
            # Nor can a forged event ID suppress a DIFFERENT signed invoice.
            other = json.dumps({"invoice_id": ASSET, "sequence": 3, "status": "settled"}).encode()
            self.assertEqual(204, self.deliver(app, other, event=PROJECT))
            with sqlite3.connect(path) as connection:
                self.assertEqual(2, connection.execute("SELECT COUNT(*) FROM wholly_inbox").fetchone()[0])

    def test_conflicting_sequence_failed_storage_and_method(self):
        with tempfile.TemporaryDirectory(prefix="wholly-python-receiver-") as folder:
            path = Path(folder) / "inbox.sqlite"
            app = receiver.create_app(SECRET, path, PROJECT)
            raw = json.dumps({"invoice_id": INVOICE, "sequence": 1, "status": "new"}).encode()
            self.assertEqual(405, self.deliver(app, raw, method="GET"))
            self.assertEqual(204, self.deliver(app, raw))
            self.assertEqual(409, self.deliver(app, raw + b" "))  # Valid HMAC, conflicting exact signed body.
            failed = receiver.create_app(SECRET, Path(folder) / "missing" / "inbox.sqlite", PROJECT)
            self.assertEqual(503, self.deliver(failed, raw))
            os.chmod(path, 0o644)
            self.assertEqual(503, self.deliver(app, raw))

    def test_database_symlink_rejected(self):
        with tempfile.TemporaryDirectory(prefix="wholly-python-receiver-") as folder:
            path = Path(folder) / "inbox.sqlite"
            path.symlink_to(Path(folder) / "other.sqlite")
            app = receiver.create_app(SECRET, path, PROJECT)
            raw = json.dumps({"invoice_id": INVOICE, "sequence": 1, "status": "new"}).encode()
            self.assertEqual(503, self.deliver(app, raw))
            self.assertFalse((Path(folder) / "other.sqlite").exists())


if __name__ == "__main__":
    unittest.main()
