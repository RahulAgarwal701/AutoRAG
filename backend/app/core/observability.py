from typing import cast

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.types import Event, Hint

from app.core.config import Settings
from app.core.logging import redact_value


def _scrub_sentry_event(event: Event, _: Hint) -> Event:
    request = event.get("request")
    if isinstance(request, dict):
        for field in ("cookies", "data", "env", "headers", "query_string"):
            request.pop(field, None)
    event.pop("user", None)
    return cast(Event, redact_value(event))


def configure_sentry(settings: Settings) -> None:
    if not settings.sentry_dsn:
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        integrations=[FastApiIntegration()],
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
        before_send=_scrub_sentry_event,
    )
