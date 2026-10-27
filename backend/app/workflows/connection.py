import base64
import binascii

from temporalio.client import Client, TLSConfig

from app.core.config import Settings, get_settings


def _secret_text(value: object) -> str | None:
    if value is None:
        return None
    getter = getattr(value, "get_secret_value", None)
    raw = getter() if callable(getter) else str(value)
    text = raw.strip()
    return text or None


def _decode_pem(value: str, label: str) -> bytes:
    normalized = value.replace("\\n", "\n").strip()
    if normalized.startswith("-----BEGIN "):
        return normalized.encode()
    try:
        decoded = base64.b64decode(normalized, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise RuntimeError(f"{label} must be PEM text or base64-encoded PEM") from exc
    if not decoded.lstrip().startswith(b"-----BEGIN "):
        raise RuntimeError(f"{label} does not contain PEM data")
    return decoded


def temporal_connection_options(settings: Settings) -> dict[str, object]:
    api_key = _secret_text(settings.temporal_api_key)
    client_cert = _secret_text(settings.temporal_mtls_cert)
    private_key = _secret_text(settings.temporal_mtls_private_key)

    if api_key and (client_cert or private_key):
        raise RuntimeError("Configure Temporal Cloud with either an API key or mTLS, not both")
    if bool(client_cert) != bool(private_key):
        raise RuntimeError(
            "TEMPORAL_MTLS_CERT and TEMPORAL_MTLS_PRIVATE_KEY must be configured together"
        )

    options: dict[str, object] = {"namespace": settings.temporal_namespace}
    if api_key:
        options.update(api_key=api_key, tls=True)
    elif client_cert and private_key:
        options["tls"] = TLSConfig(
            client_cert=_decode_pem(client_cert, "TEMPORAL_MTLS_CERT"),
            client_private_key=_decode_pem(private_key, "TEMPORAL_MTLS_PRIVATE_KEY"),
        )
    elif ".tmprl.cloud:" in settings.temporal_address:
        raise RuntimeError("Temporal Cloud requires TEMPORAL_API_KEY or both mTLS credentials")
    return options


async def connect_temporal(settings: Settings | None = None) -> Client:
    resolved = settings or get_settings()
    return await Client.connect(
        resolved.temporal_address,
        **temporal_connection_options(resolved),
    )
