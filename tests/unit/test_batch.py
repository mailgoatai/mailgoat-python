from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from mailgoat.batch import BatchError, BatchStore, build_message_payload, load_recipients, load_template, send_batch


class FakeClient:
    def __init__(self, fail_for: set[str] | None = None) -> None:
        self.fail_for = fail_for or set()
        self.sent_to: list[str] = []

    def send(self, to: str, subject: str, body: str, from_address: str | None = None) -> str:
        if to in self.fail_for:
            raise RuntimeError(f"failed:{to}")
        self.sent_to.append(to)
        return f"msg_{to}"


def test_load_recipients_from_csv(tmp_path: Path) -> None:
    csv_file = tmp_path / "recipients.csv"
    csv_file.write_text("to,subject,body\na@example.com,Hi,Body\n", encoding="utf-8")

    rows = load_recipients(csv_path=csv_file)
    assert rows[0]["to"] == "a@example.com"


def test_load_recipients_from_json(tmp_path: Path) -> None:
    json_file = tmp_path / "recipients.json"
    json_file.write_text(json.dumps([{"to": "a@example.com", "subject": "Hi", "body": "B"}]), encoding="utf-8")

    rows = load_recipients(json_path=json_file)
    assert rows[0]["subject"] == "Hi"


def test_template_substitution(tmp_path: Path) -> None:
    template_file = tmp_path / "template.json"
    template_file.write_text(json.dumps({"subject": "Hi {{name}}", "body": "Body {{id}}"}), encoding="utf-8")

    template = load_template(template_file)
    payload = build_message_payload(template, {"to": "a@example.com", "name": "Ada", "id": 123})
    assert payload["subject"] == "Hi Ada"
    assert payload["body"] == "Body 123"


def test_send_batch_continue_on_error_logs_and_completes(tmp_path: Path) -> None:
    db_path = tmp_path / "batch.db"
    error_log = tmp_path / "errors.log"
    recipients = [
        {"to": "ok@example.com", "subject": "S", "body": "B"},
        {"to": "bad@example.com", "subject": "S", "body": "B"},
    ]
    client = FakeClient(fail_for={"bad@example.com"})

    summary = send_batch(
        client=client,
        recipients=recipients,
        continue_on_error=True,
        error_log_path=error_log,
        db_path=db_path,
    )

    assert summary.sent == 1
    assert summary.failed == 1
    assert summary.status == "completed_with_errors"
    assert "bad@example.com" in error_log.read_text(encoding="utf-8")

    store = BatchStore(db_path=db_path)
    try:
        record = store.get_batch(summary.batch_id)
    finally:
        store.close()

    assert record is not None
    assert record.failed_count == 1


def test_send_batch_rate_limit(tmp_path: Path) -> None:
    db_path = tmp_path / "batch.db"
    recipients = [
        {"to": "a@example.com", "subject": "S", "body": "B"},
        {"to": "b@example.com", "subject": "S", "body": "B"},
    ]
    client = FakeClient()

    started = time.monotonic()
    send_batch(
        client=client,
        recipients=recipients,
        rate_limit=2.0,
        db_path=db_path,
    )
    elapsed = time.monotonic() - started

    # 2/sec means at least ~0.5s between two sends.
    assert elapsed >= 0.45


def test_load_recipients_invalid_selector() -> None:
    with pytest.raises(BatchError):
        load_recipients()
