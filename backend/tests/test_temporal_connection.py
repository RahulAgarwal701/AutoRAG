import base64

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.workflows.connection import temporal_connection_options


def settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_local_temporal_connection_does_not_force_tls() -> None:
    options = temporal_connection_options(settings())

    assert options == {"namespace": "default"}


def test_temporal_cloud_api_key_enables_tls() -> None:
    options = temporal_connection_options(
        settings(
            temporal_address="namespace.tmprl.cloud:7233",
            temporal_namespace="namespace.account",
            temporal_api_key=SecretStr("secret"),
        )
    )

    assert options == {
        "namespace": "namespace.account",
        "api_key": "secret",
        "tls": True,
    }


def test_temporal_cloud_accepts_base64_encoded_mtls_credentials() -> None:
    cert = base64.b64encode(b"-----BEGIN CERTIFICATE-----\ntest").decode()
    key = base64.b64encode(b"-----BEGIN PRIVATE KEY-----\ntest").decode()

    options = temporal_connection_options(
        settings(
            temporal_address="namespace.tmprl.cloud:7233",
            temporal_mtls_cert=SecretStr(cert),
            temporal_mtls_private_key=SecretStr(key),
        )
    )

    tls = options["tls"]
    assert tls.client_cert.startswith(b"-----BEGIN CERTIFICATE-----")
    assert tls.client_private_key.startswith(b"-----BEGIN PRIVATE KEY-----")


def test_temporal_cloud_rejects_missing_authentication() -> None:
    with pytest.raises(RuntimeError, match="Temporal Cloud requires"):
        temporal_connection_options(settings(temporal_address="namespace.tmprl.cloud:7233"))
