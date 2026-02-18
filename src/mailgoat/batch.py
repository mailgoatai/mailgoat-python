from __future__ import annotations

import csv
import json
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .client import MailGoat


class BatchError(Exception):
    """Raised when batch input/processing is invalid."""


@dataclass
class BatchSummary:
    batch_id: str
    total: int
    sent: int
    failed: int
    status: str
    started_at: str
    finished_at: str | None


@dataclass
class BatchRecord:
    batch_id: str
    status: str
    total_count: int
    sent_count: int
    failed_count: int
    continue_on_error: bool
    rate_limit: float | None
    started_at: str
    finished_at: str | None


class BatchStore:
    def __init__(self, db_path: str | Path = "~/.mailgoat/batches.db") -> None:
        self._path = Path(db_path).expanduser()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self._conn.close()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS batches (
                batch_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                total_count INTEGER NOT NULL,
                sent_count INTEGER NOT NULL,
                failed_count INTEGER NOT NULL,
                continue_on_error INTEGER NOT NULL,
                rate_limit REAL,
                started_at TEXT NOT NULL,
                finished_at TEXT
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS batch_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL,
                recipient TEXT,
                error TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def create_batch(
        self,
        batch_id: str,
        total_count: int,
        continue_on_error: bool,
        rate_limit: float | None,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO batches (
                batch_id, status, total_count, sent_count, failed_count,
                continue_on_error, rate_limit, started_at, finished_at
            ) VALUES (?, 'running', ?, 0, 0, ?, ?, ?, NULL)
            """,
            (
                batch_id,
                total_count,
                int(continue_on_error),
                rate_limit,
                _utc_now(),
            ),
        )
        self._conn.commit()

    def update_counts(self, batch_id: str, sent_count: int, failed_count: int) -> None:
        self._conn.execute(
            "UPDATE batches SET sent_count = ?, failed_count = ? WHERE batch_id = ?",
            (sent_count, failed_count, batch_id),
        )
        self._conn.commit()

    def complete_batch(self, batch_id: str, status: str) -> None:
        self._conn.execute(
            "UPDATE batches SET status = ?, finished_at = ? WHERE batch_id = ?",
            (status, _utc_now(), batch_id),
        )
        self._conn.commit()

    def add_error(self, batch_id: str, recipient: str | None, error: str) -> None:
        self._conn.execute(
            "INSERT INTO batch_errors (batch_id, recipient, error, created_at) VALUES (?, ?, ?, ?)",
            (batch_id, recipient, error, _utc_now()),
        )
        self._conn.commit()

    def get_batch(self, batch_id: str) -> BatchRecord | None:
        row = self._conn.execute("SELECT * FROM batches WHERE batch_id = ?", (batch_id,)).fetchone()
        if not row:
            return None
        return BatchRecord(
            batch_id=row["batch_id"],
            status=row["status"],
            total_count=int(row["total_count"]),
            sent_count=int(row["sent_count"]),
            failed_count=int(row["failed_count"]),
            continue_on_error=bool(row["continue_on_error"]),
            rate_limit=float(row["rate_limit"]) if row["rate_limit"] is not None else None,
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )


def load_recipients(
    csv_path: str | Path | None = None,
    json_path: str | Path | None = None,
    stdin_data: str | None = None,
) -> list[dict[str, Any]]:
    selected = [v is not None for v in (csv_path, json_path, stdin_data)]
    if sum(selected) != 1:
        raise BatchError("exactly one input source must be provided (csv/json/stdin)")

    if csv_path is not None:
        with Path(csv_path).open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            return [dict(row) for row in reader]

    if json_path is not None:
        payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
    else:
        payload = json.loads(stdin_data or "")

    if not isinstance(payload, list):
        raise BatchError("JSON input must be an array of recipient objects")
    parsed: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            raise BatchError("each JSON array item must be an object")
        parsed.append(item)
    return parsed


def load_template(template_path: str | Path | None) -> dict[str, Any] | None:
    if template_path is None:
        return None
    template = json.loads(Path(template_path).read_text(encoding="utf-8"))
    if not isinstance(template, dict):
        raise BatchError("template file must be a JSON object")
    return template


def render_string(value: str, data: dict[str, Any]) -> str:
    rendered = value
    for key, item in data.items():
        rendered = rendered.replace("{{" + str(key) + "}}", str(item))
    return rendered


def build_message_payload(template: dict[str, Any] | None, row: dict[str, Any]) -> dict[str, Any]:
    if template:
        subject = render_string(str(template.get("subject", "")), row)
        body = render_string(str(template.get("body", "")), row)
        from_address = template.get("from") or template.get("from_address")
    else:
        subject = str(row.get("subject", ""))
        body = str(row.get("body", ""))
        from_address = row.get("from") or row.get("from_address")

    to_value = row.get("to")
    if to_value is None:
        raise BatchError("recipient row is missing 'to'")

    return {
        "to": str(to_value),
        "subject": subject,
        "body": body,
        "from_address": str(from_address) if from_address is not None else None,
    }


def send_batch(
    client: MailGoat,
    recipients: list[dict[str, Any]],
    template: dict[str, Any] | None = None,
    continue_on_error: bool = False,
    rate_limit: float | None = None,
    error_log_path: str | Path | None = None,
    db_path: str | Path = "~/.mailgoat/batches.db",
    default_from_address: str | None = None,
) -> BatchSummary:
    batch_id = uuid4().hex
    store = BatchStore(db_path=db_path)
    store.create_batch(
        batch_id=batch_id,
        total_count=len(recipients),
        continue_on_error=continue_on_error,
        rate_limit=rate_limit,
    )

    sent = 0
    failed = 0
    delay = 0.0
    if rate_limit and rate_limit > 0:
        delay = 1.0 / rate_limit

    error_path = Path(error_log_path) if error_log_path else Path(f"batch_{batch_id}_errors.log")
    start_monotonic = time.monotonic()

    try:
        for index, row in enumerate(recipients, start=1):
            try:
                payload = build_message_payload(template, row)
                client.send(
                    to=payload["to"],
                    subject=payload["subject"],
                    body=payload["body"],
                    from_address=payload["from_address"] or default_from_address,
                )
                sent += 1
            except Exception as exc:  # noqa: BLE001
                failed += 1
                recipient = str(row.get("to")) if row.get("to") is not None else None
                message = f"recipient={recipient} error={exc}"
                with error_path.open("a", encoding="utf-8") as handle:
                    handle.write(message + "\n")
                store.add_error(batch_id=batch_id, recipient=recipient, error=str(exc))
                if not continue_on_error:
                    store.update_counts(batch_id, sent, failed)
                    store.complete_batch(batch_id, "failed")
                    raise

            store.update_counts(batch_id, sent, failed)
            _print_progress(index, len(recipients), sent, failed)

            if delay > 0 and index < len(recipients):
                elapsed = time.monotonic() - start_monotonic
                target = index * delay
                sleep_for = target - elapsed
                if sleep_for > 0:
                    time.sleep(sleep_for)

        final_status = "completed" if failed == 0 else "completed_with_errors"
        store.complete_batch(batch_id, final_status)
    finally:
        record = store.get_batch(batch_id)
        store.close()

    if record is None:
        raise BatchError("batch record was not found after completion")

    print("", file=sys.stdout)
    return BatchSummary(
        batch_id=batch_id,
        total=record.total_count,
        sent=record.sent_count,
        failed=record.failed_count,
        status=record.status,
        started_at=record.started_at,
        finished_at=record.finished_at,
    )


def _print_progress(current: int, total: int, sent: int, failed: int) -> None:
    width = 24
    completed = int((current / total) * width) if total else width
    bar = "#" * completed + "-" * (width - completed)
    print(
        f"\r[{bar}] {current}/{total} sent={sent} failed={failed}",
        end="",
        file=sys.stdout,
        flush=True,
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
