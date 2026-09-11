"""Bounded HTTP helpers. Secrets are never logged."""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Mapping, Optional, Tuple
from urllib.parse import urlparse


class HttpTransportError(RuntimeError):
    """One-shot HTTP failure with a stable failure_code."""

    def __init__(self, failure_code: str, message: str = "") -> None:
        super().__init__(message or failure_code)
        self.failure_code = failure_code


def redact_secrets(text: str, secrets: Optional[Mapping[str, str]] = None) -> str:
    """Remove known secret values from operator-visible strings."""
    redacted = text
    if secrets:
        for value in secrets.values():
            if value and value in redacted:
                redacted = redacted.replace(value, "[REDACTED]")
    for hint in ("Bearer ", "bearer "):
        if hint in redacted:
            # Collapse any remaining credential tail on the same token.
            parts = redacted.split(hint)
            rebuilt = [parts[0]]
            for part in parts[1:]:
                token = part.split(None, 1)
                if token:
                    rest = token[1] if len(token) > 1 else ""
                    rebuilt.append(hint + "[REDACTED]" + ((" " + rest) if rest else ""))
                else:
                    rebuilt.append(hint + "[REDACTED]")
            redacted = "".join(rebuilt)
    return redacted


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise HttpTransportError("redirect_rejected", "HTTP redirect rejected")


def _opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_RejectRedirects)


def post_json(
    url: str,
    body: Mapping[str, Any],
    headers: Mapping[str, str],
    *,
    timeout_s: float,
    max_response_bytes: int,
    secrets: Optional[Mapping[str, str]] = None,
) -> Tuple[int, Dict[str, Any], float, bytes]:
    """POST JSON once. Returns status, parsed JSON, elapsed_ms, raw bytes.

    Does not follow redirects, does not retry, and caps response size.
    """
    if timeout_s <= 0:
        raise HttpTransportError("invalid_timeout", "timeout_s must be > 0")
    if max_response_bytes < 1:
        raise HttpTransportError("invalid_max_response_bytes", "max_response_bytes must be >= 1")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HttpTransportError("invalid_url", "model URL must be http(s)")
    payload = json.dumps(body, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    request_headers = {str(key): str(value) for key, value in headers.items()}
    request_headers.setdefault("content-type", "application/json")
    request_headers.setdefault("accept", "application/json")
    request = urllib.request.Request(
        url,
        data=payload,
        headers=request_headers,
        method="POST",
    )
    started = time.perf_counter()
    deadline = started + timeout_s
    try:
        with _opener().open(request, timeout=timeout_s) as response:
            status = int(getattr(response, "status", response.getcode()))
            if 300 <= status < 400:
                raise HttpTransportError("redirect_rejected", "HTTP redirect rejected")
            raw = _read_bounded(response, max_response_bytes, deadline=deadline)
    except HttpTransportError:
        raise
    except urllib.error.HTTPError as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if 300 <= int(exc.code) < 400:
            raise HttpTransportError("redirect_rejected", "HTTP redirect rejected") from exc
        try:
            raw = _read_bounded(exc, max_response_bytes, deadline=deadline)
        except HttpTransportError as size_error:
            raise size_error from exc
        except Exception:
            raw = b""
        return int(exc.code), {}, elapsed_ms, raw
    except socket.timeout as exc:
        raise HttpTransportError("timeout", "request timed out") from exc
    except TimeoutError as exc:
        raise HttpTransportError("timeout", "request timed out") from exc
    except urllib.error.URLError as exc:
        reason = exc.reason
        message = redact_secrets(str(reason), secrets)
        if isinstance(reason, socket.timeout) or "timed out" in message.lower():
            raise HttpTransportError("timeout", "request timed out") from exc
        if "redirect" in message.lower():
            raise HttpTransportError("redirect_rejected", "HTTP redirect rejected") from exc
        raise HttpTransportError("model_http_error", message) from exc
    except Exception as exc:  # noqa: BLE001 - convert to stable failure code
        message = redact_secrets(str(exc), secrets)
        if "timed out" in message.lower():
            raise HttpTransportError("timeout", "request timed out") from exc
        raise HttpTransportError("model_http_error", message) from exc
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    parsed_json: Dict[str, Any] = {}
    if raw:
        try:
            loaded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HttpTransportError("invalid_json", "response was not JSON") from exc
        if not isinstance(loaded, dict):
            raise HttpTransportError("invalid_json", "response JSON root must be an object")
        parsed_json = loaded
    return status, parsed_json, elapsed_ms, raw


def _read_bounded(response: Any, max_bytes: int, *, deadline: Optional[float] = None) -> bytes:
    if max_bytes < 1:
        raise HttpTransportError("invalid_max_response_bytes", "max_response_bytes must be >= 1")
    length_header = None
    headers = getattr(response, "headers", None)
    if headers is not None:
        length_header = headers.get("Content-Length") or headers.get("content-length")
    if length_header is not None:
        try:
            if int(length_header) > max_bytes:
                raise HttpTransportError("response_too_large", "response exceeds size limit")
        except ValueError:
            pass
    chunks = []
    received = 0
    while True:
        if deadline is not None and time.perf_counter() > deadline:
            raise HttpTransportError("timeout", "request timed out")
        remaining = max_bytes - received
        if remaining <= 0:
            raise HttpTransportError("response_too_large", "response exceeds size limit")
        chunk = response.read(min(65536, remaining))
        if not chunk:
            break
        received += len(chunk)
        if received > max_bytes:
            raise HttpTransportError("response_too_large", "response exceeds size limit")
        chunks.append(chunk)
    return b"".join(chunks)
