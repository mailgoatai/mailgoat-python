from __future__ import annotations

import json
import os
from pathlib import Path

from mailgoat.cli import main
from mailgoat.batch import BatchStore
from mailgoat.profiles import MailProfile, ProfileStore


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


def test_profile_list_and_use(tmp_path: Path, capsys) -> None:
    config = tmp_path / "profiles.json"
    store = ProfileStore(config_path=config)
    store.add_profile(MailProfile(name="work", server="https://postal.work", api_key="k1"), make_default=True)
    store.add_profile(MailProfile(name="home", server="https://postal.home", api_key="k2"))

    list_code = main(["profile", "--config-path", str(config), "list"])
    list_output = json.loads(capsys.readouterr().out.strip())
    assert list_code == 0
    assert list_output["default_profile"] == "work"

    use_code = main(["profile", "--config-path", str(config), "use", "home"])
    use_output = json.loads(capsys.readouterr().out.strip())
    assert use_code == 0
    assert use_output["default_profile"] == "home"


def test_send_batch_uses_env_profile(monkeypatch, tmp_path: Path, capsys) -> None:
    config = tmp_path / "profiles.json"
    db_path = tmp_path / "batch.db"
    json_path = tmp_path / "recipients.json"
    json_path.write_text('[{\"to\":\"user@example.com\",\"subject\":\"S\",\"body\":\"B\"}]', encoding="utf-8")

    store = ProfileStore(config_path=config)
    store.add_profile(
        MailProfile(
            name="work",
            server="https://postal.work",
            api_key="key-work",
            from_address="sender@example.com",
            from_name="Sender",
        ),
        make_default=True,
    )

    monkeypatch.setenv("MAILGOAT_PROFILE", "work")
    monkeypatch.setattr("mailgoat.cli.ProfileStore", lambda: ProfileStore(config_path=config))

    captured: dict[str, str | None] = {}

    class FakeMailGoat:
        def __init__(self, server: str, api_key: str) -> None:
            captured["server"] = server
            captured["api_key"] = api_key

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

    def fake_send_batch(**kwargs):
        captured["from_address"] = kwargs.get("default_from_address")
        class Summary:
            batch_id = "b1"
            status = "completed"
            total = 1
            sent = 1
            failed = 0
            started_at = "start"
            finished_at = "finish"
        return Summary()

    monkeypatch.setattr("mailgoat.cli.MailGoat", FakeMailGoat)
    monkeypatch.setattr("mailgoat.cli.send_batch", fake_send_batch)

    code = main(["send-batch", "--json", str(json_path), "--db-path", str(db_path)])
    output = json.loads(capsys.readouterr().out.strip().splitlines()[-1])

    assert code == 0
    assert captured["server"] == "https://postal.work"
    assert captured["api_key"] == "key-work"
    assert captured["from_address"] == "sender@example.com"
    assert output["batch_id"] == "b1"


def test_send_batch_profile_flag_overrides_env(monkeypatch, tmp_path: Path, capsys) -> None:
    config = tmp_path / "profiles.json"
    db_path = tmp_path / "batch.db"
    json_path = tmp_path / "recipients.json"
    json_path.write_text('[{\"to\":\"user@example.com\",\"subject\":\"S\",\"body\":\"B\"}]', encoding="utf-8")

    store = ProfileStore(config_path=config)
    store.add_profile(MailProfile(name="work", server="https://postal.work", api_key="k1"), make_default=True)
    store.add_profile(MailProfile(name="home", server="https://postal.home", api_key="k2"))

    monkeypatch.setenv("MAILGOAT_PROFILE", "work")
    monkeypatch.setattr("mailgoat.cli.ProfileStore", lambda: ProfileStore(config_path=config))

    seen: dict[str, str | None] = {}

    class FakeMailGoat:
        def __init__(self, server: str, api_key: str) -> None:
            seen["server"] = server
            seen["api_key"] = api_key

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

    def fake_send_batch(**kwargs):
        class Summary:
            batch_id = "b2"
            status = "completed"
            total = 1
            sent = 1
            failed = 0
            started_at = "start"
            finished_at = "finish"
        return Summary()

    monkeypatch.setattr("mailgoat.cli.MailGoat", FakeMailGoat)
    monkeypatch.setattr("mailgoat.cli.send_batch", fake_send_batch)

    code = main(["send-batch", "--profile", "home", "--json", str(json_path), "--db-path", str(db_path)])
    _ = capsys.readouterr().out.strip()

    assert code == 0
    assert seen["server"] == "https://postal.home"
    assert seen["api_key"] == "k2"
