from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from mailgoat import MailGoat, MailGoatAPIError, MailGoatNetworkError


@respx.mock
def test_send_returns_message_id() -> None:
    route = respx.post("https://mailgoat.example/api/v1/send/message").respond(
        status_code=200,
        json={"data": {"message": {"id": "msg_123"}}},
    )

    client = MailGoat("https://mailgoat.example", "test-key")
    message_id = client.send(to="user@example.com", subject="Hello", body="World")

    assert route.called
    assert message_id == "msg_123"


@respx.mock
def test_read_returns_message() -> None:
    respx.get("https://mailgoat.example/api/v1/messages/msg_123").respond(
        status_code=200,
        json={
            "id": "msg_123",
            "to": ["user@example.com"],
            "from": "sender@example.com",
            "subject": "Hello",
            "body": "World",
        },
    )

    client = MailGoat("https://mailgoat.example", "test-key")
    message = client.read("msg_123")

    assert message.id == "msg_123"
    assert message.to == ["user@example.com"]
    assert message.subject == "Hello"


@respx.mock
def test_send_raises_api_error() -> None:
    respx.post("https://mailgoat.example/api/v1/send/message").respond(
        status_code=401,
        json={"error": "invalid API key"},
    )

    client = MailGoat("https://mailgoat.example", "bad-key")

    with pytest.raises(MailGoatAPIError) as err:
        client.send(to="user@example.com", subject="Hello", body="World")

    assert err.value.status_code == 401


@respx.mock
def test_send_raises_api_error_when_status_error_envelope() -> None:
    respx.post("https://mailgoat.example/api/v1/send/message").respond(
        status_code=200,
        json={
            "status": "error",
            "data": {"message": "The API token provided in X-Server-API-Key was not valid."},
        },
    )

    client = MailGoat("https://mailgoat.example", "bad-key")

    with pytest.raises(MailGoatAPIError) as err:
        client.send(to="user@example.com", subject="Hello", body="World")

    assert err.value.status_code == 200


@respx.mock
def test_send_raises_network_error() -> None:
    def raise_timeout(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout")

    respx.post("https://mailgoat.example/api/v1/send/message").mock(side_effect=raise_timeout)

    client = MailGoat("https://mailgoat.example", "test-key")

    with pytest.raises(MailGoatNetworkError):
        client.send(to="user@example.com", subject="Hello", body="World")


@respx.mock
def test_send_with_attachment(tmp_path: Path) -> None:
    attachment = tmp_path / "note.txt"
    attachment.write_text("hello", encoding="utf-8")

    route = respx.post("https://mailgoat.example/api/v1/send/message").respond(
        status_code=200,
        json={"id": "msg_456"},
    )

    client = MailGoat("https://mailgoat.example", "test-key")
    result = client.send(
        to=["user@example.com"],
        subject="Attachment",
        body="See file",
        attachments=[attachment],
    )

    assert route.called
    assert result == "msg_456"
