from __future__ import annotations

from pathlib import Path

from mailgoat.profiles import MailProfile, ProfileStore, prompt_for_profile


def test_add_list_and_default_profile(tmp_path: Path) -> None:
    store = ProfileStore(config_path=tmp_path / "profiles.json")
    store.add_profile(
        MailProfile(
            name="work",
            server="https://postal.work",
            api_key="key-work",
            from_address="work@example.com",
            from_name="Work",
        ),
        make_default=True,
    )
    store.add_profile(
        MailProfile(
            name="personal",
            server="https://postal.home",
            api_key="key-home",
            from_address="me@example.com",
            from_name="Me",
        )
    )

    assert store.get_default_profile_name() == "work"
    names = [profile.name for profile in store.list_profiles()]
    assert names == ["personal", "work"]


def test_set_default_profile(tmp_path: Path) -> None:
    store = ProfileStore(config_path=tmp_path / "profiles.json")
    store.add_profile(MailProfile(name="a", server="s", api_key="k"), make_default=True)
    store.add_profile(MailProfile(name="b", server="s2", api_key="k2"))

    store.set_default("b")

    assert store.get_default_profile_name() == "b"


def test_prompt_for_profile(monkeypatch) -> None:
    answers = iter(["https://postal.example.com", "sender@example.com", "Sender Name"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    monkeypatch.setattr("getpass.getpass", lambda _: "secret-key")

    profile = prompt_for_profile("demo")

    assert profile.name == "demo"
    assert profile.server == "https://postal.example.com"
    assert profile.api_key == "secret-key"
    assert profile.from_address == "sender@example.com"
