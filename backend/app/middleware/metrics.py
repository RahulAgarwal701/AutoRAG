import threading
import time
from collections import defaultdict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


class RequestMetricStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: dict[tuple[str, str, int], int] = defaultdict(int)
        self._duration_buckets: dict[tuple[str, str], list[int]] = defaultdict(
            lambda: [0] * len(_BUCKETS)
        )
        self._duration_sums: dict[tuple[str, str], float] = defaultdict(float)
        self._duration_counts: dict[tuple[str, str], int] = defaultdict(int)
        self._in_progress = 0

    def started(self) -> None:
        with self._lock:
            self._in_progress += 1

    def finished(self, *, method: str, route: str, status_code: int, duration: float) -> None:
        with self._lock:
            self._in_progress -= 1
            self._requests[(method, route, status_code)] += 1
            key = (method, route)
            for index, bucket in enumerate(_BUCKETS):
                if duration <= bucket:
                    self._duration_buckets[key][index] += 1
            self._duration_sums[key] += duration
            self._duration_counts[key] += 1

    def render(self) -> str:
        with self._lock:
            requests = dict(self._requests)
            buckets = {key: list(values) for key, values in self._duration_buckets.items()}
            sums = dict(self._duration_sums)
            counts = dict(self._duration_counts)
            in_progress = self._in_progress
        lines = [
            "# HELP autorag_http_requests_total Total HTTP requests.",
            "# TYPE autorag_http_requests_total counter",
        ]
        for (method, route, status_code), count in sorted(requests.items()):
            labels = _labels(method=method, route=route, status=str(status_code))
            lines.append(f"autorag_http_requests_total{{{labels}}} {count}")
        lines.extend(
            [
                "# HELP autorag_http_request_duration_seconds HTTP request latency.",
                "# TYPE autorag_http_request_duration_seconds histogram",
            ]
        )
        for (method, route), bucket_counts in sorted(buckets.items()):
            base = _labels(method=method, route=route)
            for bucket, count in zip(_BUCKETS, bucket_counts, strict=True):
                lines.append(
                    "autorag_http_request_duration_seconds_bucket"
                    f'{{{base},le="{bucket:g}"}} {count}'
                )
            lines.append(
                "autorag_http_request_duration_seconds_bucket"
                f'{{{base},le="+Inf"}} {counts[(method, route)]}'
            )
            lines.append(
                f"autorag_http_request_duration_seconds_sum{{{base}}} {sums[(method, route)]:.9f}"
            )
            lines.append(
                f"autorag_http_request_duration_seconds_count{{{base}}} {counts[(method, route)]}"
            )
        lines.extend(
            [
                "# HELP autorag_http_requests_in_progress HTTP requests currently running.",
                "# TYPE autorag_http_requests_in_progress gauge",
                f"autorag_http_requests_in_progress {in_progress}",
                "",
            ]
        )
        return "\n".join(lines)


def _labels(**values: str) -> str:
    return ",".join(
        f'{key}="{value.replace(chr(92), chr(92) * 2).replace(chr(34), chr(92) + chr(34))}"'
        for key, value in values.items()
    )


request_metrics = RequestMetricStore()


class RequestMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_metrics.started()
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            route_object = request.scope.get("route")
            route = getattr(route_object, "path", "__unmatched__")
            request_metrics.finished(
                method=request.method,
                route=str(route),
                status_code=status_code,
                duration=time.perf_counter() - started,
            )
