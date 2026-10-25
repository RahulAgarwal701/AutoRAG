from dataclasses import dataclass, field


@dataclass
class PublicApiError(Exception):
    status_code: int
    code: str
    message: str
    headers: dict[str, str] = field(default_factory=dict)

