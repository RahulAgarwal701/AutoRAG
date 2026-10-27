from pytest import MonkeyPatch

from app.core.config import Settings


def test_cors_origins_accept_comma_separated_value(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000, https://app.example.com")

    settings = Settings(_env_file=None)

    assert settings.cors_origins == ["http://localhost:3000", "https://app.example.com"]


def test_blank_optional_api_keys_are_not_treated_as_configured(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("XAI_API_KEY", "   ")

    settings = Settings(_env_file=None)

    assert settings.gemini_api_key is None
    assert settings.xai_api_key is None


def test_render_postgres_url_uses_asyncpg_driver(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://autorag:secret@database.internal:5432/autorag")

    settings = Settings(_env_file=None)

    assert settings.database_url == (
        "postgresql+asyncpg://autorag:secret@database.internal:5432/autorag"
    )


def test_blank_optional_cors_regex_is_none(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGIN_REGEX", "")

    settings = Settings(_env_file=None)

    assert settings.cors_origin_regex is None
