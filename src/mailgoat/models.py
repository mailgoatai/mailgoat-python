from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    """Represents a message returned by the MailGoat API."""

    id: str
    to: list[str] = field(default_factory=list)
    from_address: str | None = None
    subject: str | None = None
    body: str | None = None
    status: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "Message":
        to_value = payload.get("to")
        if isinstance(to_value, str):
            recipients = [to_value]
        elif isinstance(to_value, list):
            recipients = [str(item) for item in to_value]
        else:
            recipients = []

        return cls(
            id=str(payload.get("id") or payload.get("message_id") or ""),
            to=recipients,
            from_address=payload.get("from") or payload.get("from_address"),
            subject=payload.get("subject"),
            body=payload.get("body") or payload.get("plain_body") or payload.get("text_body"),
            status=payload.get("status"),
            raw=payload,
        )
