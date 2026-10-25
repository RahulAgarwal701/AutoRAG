from pytest import MonkeyPatch

from app.core.config import Settings


def test_cors_origins_accept_comma_separated_value(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000, https://app.example.com")

    settings = Settings(_env_file=None)

    assert settings.cors_origins == ["http://localhost:3000", "https://app.example.com"]

