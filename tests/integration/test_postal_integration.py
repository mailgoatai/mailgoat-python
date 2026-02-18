from __future__ import annotations

import os

import pytest

from mailgoat import MailGoat


pytestmark = pytest.mark.integration


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        pytest.skip(f"Missing required env var: {name}")
    return value


def test_send_and_read_against_postal() -> None:
    server = _require_env("MAILGOAT_TEST_SERVER")
    api_key = _require_env("MAILGOAT_TEST_API_KEY")
    to_address = _require_env("MAILGOAT_TEST_TO")

    client = MailGoat(server=server, api_key=api_key)

    message_id = client.send(
        to=to_address,
        subject="MailGoat integration test",
        body="This is an integration test message.",
    )

    assert message_id

    message = client.read(message_id)
    assert message.id == message_id
