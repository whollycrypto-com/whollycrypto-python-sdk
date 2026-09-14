"""Durable IPN/webhook inbox example (WSGI, standard library).

Mount create_app() behind your HTTPS application server; this file starts no server.
Works for IPN or webhooks; see ipn-webhooks.md and notification.json beside this file.
IPN uses the Store -> IPN secret; a webhook uses its own endpoint secret, not an API token.
Use one configured project and signing secret per endpoint. Create a private 0700
directory outside your web root for the database. It is not a fulfilment worker:
your worker must re-fetch the invoice, match the stored order/project/store/amount
and update order state transactionally exactly once. Retain replay guards for at
least your application's entire delivery/redelivery window.
"""

from __future__ import annotations

import os
import json
import re
import sqlite3
import stat
from pathlib import Path

from whollycrypto import InvalidSignatureError, parse_notification


def invoice_state(payload):
    """Compare invoice revision fields, not event IDs, market snapshots or JSON formatting."""
    fields = ("invoice_id", "status", "amount_status", "timing_status", "resolution", "sequence", "amount", "currency", "order_id")
    return tuple(str(payload.get(key, "")) if key == "sequence" else payload.get(key) for key in fields)


def create_app(signing_secret: str, queue_path: str | Path, project_id: str):
    if not isinstance(signing_secret, str) or not signing_secret:
        raise ValueError("Configure a store's IPN/webhook signing secret.")
    if not re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", project_id):
        raise ValueError("Configure the Project API UUID for this endpoint.")
    path = Path(queue_path)
    if not path.is_absolute():
        raise ValueError("Use an absolute private inbox database path.")

    def app(environ, start_response):
        def respond(status, headers=()):
            start_response(status, [("Content-Length", "0"), ("Cache-Control", "no-store"), *headers])
            return [b""]

        if environ.get("REQUEST_METHOD") != "POST":
            return respond("405 Method Not Allowed", [("Allow", "POST")])
        length = environ.get("CONTENT_LENGTH", "")
        if not isinstance(length, str) or not re.fullmatch(r"[0-9]{1,6}", length):
            return respond("411 Length Required")
        if int(length) > 262_144:
            return respond("413 Content Too Large")
        raw = environ["wsgi.input"].read(int(length))
        if len(raw) != int(length):
            return respond("400 Bad Request")
        try:
            notice = parse_notification(
                raw,
                {
                    "Wholly-Signature": environ.get("HTTP_WHOLLY_SIGNATURE", ""),
                    "Wholly-Event-Id": environ.get("HTTP_WHOLLY_EVENT_ID", ""),
                    "Wholly-Delivery-Id": environ.get("HTTP_WHOLLY_DELIVERY_ID", ""),
                },
                signing_secret,
            )
        except InvalidSignatureError:
            return respond("400 Bad Request")

        if notice.payload.get("project_id", project_id).lower() != project_id.lower():
            return respond("400 Bad Request")

        connection = None
        try:
            # Authenticate BEFORE touching the filesystem. The configured directory
            # must be private and controlled by the application user.
            parent = path.parent.lstat()
            if not stat.S_ISDIR(parent.st_mode) or parent.st_mode & 0o077:
                raise OSError("Private directory required")
            if hasattr(os, "getuid") and parent.st_uid != os.getuid():
                raise OSError("Unexpected directory owner")
            try:
                descriptor = os.open(
                    path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600
                )
                os.close(descriptor)
            except FileExistsError:
                pass
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
                raise OSError("Private regular database required")
            if hasattr(os, "getuid") and info.st_uid != os.getuid():
                raise OSError("Unexpected database owner")
            connection = sqlite3.connect(path, timeout=5)
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("""CREATE TABLE IF NOT EXISTS wholly_inbox (
                project_id TEXT NOT NULL, invoice_id TEXT NOT NULL, sequence INTEGER NOT NULL,
                event_id TEXT NOT NULL, delivery_id TEXT NOT NULL, payload BLOB NOT NULL,
                processed_at TEXT, received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (project_id, invoice_id, sequence)
            )""")
            with connection:
                connection.execute(
                    """INSERT OR IGNORE INTO wholly_inbox
                    (project_id, invoice_id, sequence, event_id, delivery_id, payload)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        project_id.lower(),
                        notice.invoice_id.lower(),
                        notice.sequence,
                        notice.event_id,
                        notice.delivery_id,
                        raw,
                    ),
                )
                existing = connection.execute(
                    "SELECT payload FROM wholly_inbox WHERE project_id=? AND invoice_id=? AND sequence=?",
                    (project_id.lower(), notice.invoice_id.lower(), notice.sequence),
                ).fetchone()
                if existing is None or invoice_state(json.loads(existing[0])) != invoice_state(notice.payload):
                    # A conflicting signed snapshot needs review, not a silent acknowledgement.
                    return respond("409 Conflict")
            return respond("204 No Content")  # Only after the transaction is durable.
        except (OSError, sqlite3.Error, ValueError, TypeError):
            # Never acknowledge failed storage or print customer payloads/secrets.
            return respond("503 Service Unavailable")
        finally:
            if connection is not None:
                connection.close()

    return app
