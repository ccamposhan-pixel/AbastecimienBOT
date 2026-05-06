from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LLMHTTPError(RuntimeError):
    pass


@dataclass(frozen=True)
class HTTPResponse:
    status: int
    body: dict[str, Any]


def post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
    timeout_seconds: float = 30.0,
) -> HTTPResponse:
    data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Accept", "application/json")
    for key, value in (headers or {}).items():
        request.add_header(key, value)

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="replace")
            body = json.loads(raw) if raw.strip() else {}
            return HTTPResponse(status=int(getattr(response, "status", 200)), body=body)
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
        detail = raw.strip() or str(exc)
        raise LLMHTTPError(f"HTTP {exc.code} calling LLM endpoint: {detail}") from exc
    except URLError as exc:
        raise LLMHTTPError(f"Network error calling LLM endpoint: {exc}") from exc

