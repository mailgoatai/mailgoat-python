from __future__ import annotations

import getpass
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ProfileError(Exception):
    """Raised when profile state is invalid."""


@dataclass
class MailProfile:
    name: str
    server: str
    api_key: str
    from_address: str | None = None
    from_name: str | None = None


class ProfileStore:
    def __init__(self, config_path: str | Path = "~/.mailgoat/profiles.json") -> None:
        self._path = Path(config_path).expanduser()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {"default_profile": None, "profiles": {}}
        data = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ProfileError("profile config must be a JSON object")
        data.setdefault("default_profile", None)
        data.setdefault("profiles", {})
        return data

    def save(self, data: dict[str, Any]) -> None:
        self._path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def add_profile(self, profile: MailProfile, make_default: bool = False) -> None:
        data = self.load()
        profiles = data["profiles"]
        profiles[profile.name] = {
            "server": profile.server,
            "api_key": profile.api_key,
            "from_address": profile.from_address,
            "from_name": profile.from_name,
        }
        if make_default or data.get("default_profile") is None:
            data["default_profile"] = profile.name
        self.save(data)

    def set_default(self, name: str) -> None:
        data = self.load()
        if name not in data["profiles"]:
            raise ProfileError(f"profile not found: {name}")
        data["default_profile"] = name
        self.save(data)

    def list_profiles(self) -> list[MailProfile]:
        data = self.load()
        rows: list[MailProfile] = []
        for name, profile_data in data["profiles"].items():
            rows.append(
                MailProfile(
                    name=name,
                    server=str(profile_data.get("server", "")),
                    api_key=str(profile_data.get("api_key", "")),
                    from_address=profile_data.get("from_address"),
                    from_name=profile_data.get("from_name"),
                )
            )
        return sorted(rows, key=lambda p: p.name)

    def get_profile(self, name: str) -> MailProfile:
        data = self.load()
        profile_data = data["profiles"].get(name)
        if not isinstance(profile_data, dict):
            raise ProfileError(f"profile not found: {name}")
        return MailProfile(
            name=name,
            server=str(profile_data.get("server", "")),
            api_key=str(profile_data.get("api_key", "")),
            from_address=profile_data.get("from_address"),
            from_name=profile_data.get("from_name"),
        )

    def get_default_profile_name(self) -> str | None:
        data = self.load()
        value = data.get("default_profile")
        return str(value) if value else None


def prompt_for_profile(name: str) -> MailProfile:
    server = input("Server URL: ").strip()
    api_key = getpass.getpass("API key: ").strip()
    from_address = input("From address (optional): ").strip() or None
    from_name = input("From name (optional): ").strip() or None
    if not server:
        raise ProfileError("server is required")
    if not api_key:
        raise ProfileError("api_key is required")
    return MailProfile(
        name=name,
        server=server,
        api_key=api_key,
        from_address=from_address,
        from_name=from_name,
    )
