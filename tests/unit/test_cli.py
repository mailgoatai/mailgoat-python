from __future__ import annotations

import json
from pathlib import Path

from mailgoat.cli import main
from mailgoat.batch import BatchStore


def test_batch_status_command(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "batch.db"
    store = BatchStore(db_path=db_path)
    try:
        store.create_batch("batch123", total_count=10, continue_on_error=True, rate_limit=5.0)
        store.update_counts("batch123", sent_count=3, failed_count=1)
        store.complete_batch("batch123", status="completed_with_errors")
    finally:
        store.close()

    code = main(["batch", "status", "batch123", "--db-path", str(db_path)])
    captured = capsys.readouterr().out.strip()

    assert code == 0
    payload = json.loads(captured)
    assert payload["batch_id"] == "batch123"
    assert payload["failed"] == 1


def test_batch_status_not_found(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "batch.db"
    code = main(["batch", "status", "missing", "--db-path", str(db_path)])
    captured = capsys.readouterr().out.strip()

    assert code == 1
    payload = json.loads(captured)
    assert payload["error"] == "batch not found"
