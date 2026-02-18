from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from .models import Message


class MailGoatError(Exception):
    """Base exception for MailGoat SDK errors."""


class MailGoatAPIError(MailGoatError):
    """Raised when the MailGoat API returns an error response."""

    def __init__(self, status_code: int, message: str, payload: Any | None = None) -> None:
        super().__init__(f"MailGoat API error ({status_code}): {message}")
        self.status_code = status_code
        self.payload = payload


class MailGoatNetworkError(MailGoatError):
    """Raised when network failures occur while talking to MailGoat."""


class MailGoat:
    """MailGoat HTTP API client."""

    def __init__(self, server: str, api_key: str, timeout: float = 15.0) -> None:
        self._server = server.rstrip("/")
        self._api_key = api_key
        self._client = httpx.Client(
            base_url=self._server,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Accept": "application/json",
                "User-Agent": "mailgoat-python/1.0.0b1",
            },
        )

    def send(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        from_address: str | None = None,
        attachments: list[str | Path] | None = None,
    ) -> str:
        files = self._build_attachments(attachments)
        payload: dict[str, Any] = {
            "to": [to] if isinstance(to, str) else to,
            "subject": subject,
            "body": body,
        }
        if from_address:
            payload["from"] = from_address

        try:
            response = self._client.post("/api/v1/messages/send", data=payload, files=files or None)
        except httpx.HTTPError as exc:
            raise MailGoatNetworkError(str(exc)) from exc
        finally:
            for _, (_, handle, _) in files:
                handle.close()

        data = self._parse_response(response)
        message_id = data.get("message_id") or data.get("id")
        if not message_id:
            raise MailGoatAPIError(response.status_code, "missing message_id in API response", data)
        return str(message_id)

    def read(self, message_id: str) -> Message:
        try:
            response = self._client.get(f"/api/v1/messages/{message_id}")
        except httpx.HTTPError as exc:
            raise MailGoatNetworkError(str(exc)) from exc

        data = self._parse_response(response)
        return Message.from_api(data)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "MailGoat":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def _parse_response(self, response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError:
            data = None

        if response.status_code >= 400:
            if isinstance(data, dict):
                message = str(data.get("error") or data.get("message") or "unknown API error")
            else:
                message = response.text or "unknown API error"
            raise MailGoatAPIError(response.status_code, message, data)

        if not isinstance(data, dict):
            raise MailGoatAPIError(response.status_code, "invalid JSON response from API", data)
        return data

    def _build_attachments(
        self, attachments: list[str | Path] | None
    ) -> list[tuple[str, tuple[str, Any, str]]]:
        if not attachments:
            return []

        files: list[tuple[str, tuple[str, Any, str]]] = []
        for item in attachments:
            path = Path(item)
            handle = path.open("rb")
            files.append(("attachments", (path.name, handle, "application/octet-stream")))
        return files
