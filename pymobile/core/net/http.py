"""HTTP client built on the standard library.

Why not ``requests``? Every dependency bundled into an APK costs download size
and build time, and ``urllib`` already covers GET/POST/PUT/DELETE. The client
adds the parts that are genuinely missing: JSON handling, timeouts, retries
with backoff, a base URL and default headers.
"""

from __future__ import annotations

import json as jsonlib
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ... import __version__
from ...errors import NetworkError
from ...logging import get_logger

__all__ = ["HttpClient", "Response", "DEFAULT_TIMEOUT"]

_log = get_logger("http")

DEFAULT_TIMEOUT = 15.0
#: Retryable statuses: the documented 408/425/429 plus every 5xx.
_RETRY_STATUSES = frozenset({408, 425, 429})
Params = Mapping[str, str | int | float | bool | None]


@dataclass(frozen=True, slots=True)
class Response:
    """An immutable HTTP response."""

    status: int
    headers: dict[str, str]
    content: bytes
    url: str
    elapsed: float = 0.0
    encoding: str = "utf-8"

    @property
    def ok(self) -> bool:
        """``True`` for 2xx status codes."""
        return 200 <= self.status < 300

    @property
    def text(self) -> str:
        """Body decoded as text (invalid bytes are replaced, never raised)."""
        return self.content.decode(self.encoding, errors="replace")

    def json(self) -> Any:
        """Parse the body as JSON."""
        if not self.content:
            raise NetworkError("Response body is empty; nothing to decode as JSON")
        try:
            return jsonlib.loads(self.text)
        except ValueError as exc:
            preview = self.text[:120]
            raise NetworkError(
                f"Response from {self.url} is not valid JSON: {exc}",
                hint=f"First bytes of the body: {preview!r}",
            ) from exc

    def raise_for_status(self) -> Response:
        """Return ``self``, or raise :class:`NetworkError` for 4xx/5xx."""
        if not self.ok:
            raise NetworkError(
                f"HTTP {self.status} for {self.url}",
                hint=self.text[:200] or None,
            )
        return self


@dataclass(slots=True)
class HttpClient:
    """A small, synchronous HTTP client.

    ``retries`` applies to connection errors and to retryable status codes
    (408/425/429 and 5xx) with exponential backoff.
    """

    base_url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    timeout: float = DEFAULT_TIMEOUT
    retries: int = 0
    backoff: float = 0.5
    user_agent: str = f"PyMobile/{__version__}"

    # -- verbs -------------------------------------------------------------
    def get(self, url: str, *, params: Params | None = None, **kwargs: Any) -> Response:
        """Perform a GET request."""
        return self.request("GET", url, params=params, **kwargs)

    def post(self, url: str, **kwargs: Any) -> Response:
        """Perform a POST request."""
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> Response:
        """Perform a PUT request."""
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> Response:
        """Perform a DELETE request."""
        return self.request("DELETE", url, **kwargs)

    # -- core --------------------------------------------------------------
    def request(
        self,
        method: str,
        url: str,
        *,
        params: Params | None = None,
        json: Any = None,
        data: bytes | str | Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> Response:
        """Send a request and return a :class:`Response`.

        Raises :class:`~pymobile.errors.NetworkError` on transport failures;
        HTTP error statuses are returned, not raised (use
        :meth:`Response.raise_for_status`).
        """
        if json is not None and data is not None:
            raise ValueError("pass either json= or data=, not both")

        final_url = self._build_url(url, params)
        body, content_type = self._encode_body(json, data)
        request_headers = self._merge_headers(headers, content_type)
        attempts = max(0, self.retries) + 1
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            started = time.monotonic()
            try:
                response = self._send(method.upper(), final_url, body, request_headers, timeout)
            except NetworkError as exc:
                last_error = exc
                if attempt >= attempts:
                    raise
                self._sleep(attempt)
                _log.debug("retrying %s %s (%s)", method, final_url, exc)
                continue

            elapsed = time.monotonic() - started
            response = Response(
                status=response.status,
                headers=response.headers,
                content=response.content,
                url=response.url,
                elapsed=elapsed,
                encoding=response.encoding,
            )
            if (
                response.status in _RETRY_STATUSES or response.status >= 500
            ) and attempt < attempts:
                self._sleep(attempt)
                _log.debug("retrying %s %s after HTTP %s", method, final_url, response.status)
                continue
            _log.debug("%s %s -> %s in %.0f ms", method, final_url, response.status, elapsed * 1000)
            return response

        raise NetworkError(str(last_error) if last_error else "Request failed")

    def _send(
        self,
        method: str,
        url: str,
        body: bytes | None,
        headers: dict[str, str],
        timeout: float | None,
    ) -> Response:
        """One transport attempt."""
        request = urllib.request.Request(url, data=body, method=method)
        for key, value in headers.items():
            request.add_header(key, value)
        try:
            with urllib.request.urlopen(
                request, timeout=timeout if timeout is not None else self.timeout
            ) as raw:
                return self._to_response(raw.geturl(), raw.status, dict(raw.headers), raw.read())
        except urllib.error.HTTPError as exc:  # 4xx/5xx are valid responses here
            payload = exc.read() if hasattr(exc, "read") else b""
            return self._to_response(url, int(exc.code), dict(exc.headers or {}), payload)
        except urllib.error.URLError as exc:
            raise NetworkError(
                f"Could not reach {url}: {exc.reason}",
                hint="Check connectivity and the INTERNET permission in your project config.",
            ) from exc
        except TimeoutError as exc:
            raise NetworkError(f"Request to {url} timed out") from exc

    @staticmethod
    def _to_response(url: str, status: int, headers: Mapping[str, str], content: bytes) -> Response:
        """Build a Response, honouring the charset from ``Content-Type``."""
        normalized = {key.lower(): value for key, value in headers.items()}
        encoding = "utf-8"
        content_type = normalized.get("content-type", "")
        if "charset=" in content_type:
            encoding = content_type.split("charset=", 1)[1].split(";")[0].strip() or "utf-8"
        return Response(
            status=status, headers=normalized, content=content, url=url, encoding=encoding
        )

    # -- helpers -----------------------------------------------------------
    def _build_url(self, url: str, params: Params | None) -> str:
        """Join the base URL and append the query string."""
        full = url
        if self.base_url and not urllib.parse.urlparse(url).scheme:
            full = f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"
        scheme = urllib.parse.urlparse(full).scheme
        if scheme not in ("http", "https"):
            raise NetworkError(
                f"Unsupported URL scheme in {full!r}",
                hint="Only http:// and https:// URLs are allowed.",
            )
        if params:
            filtered = {k: str(v) for k, v in params.items() if v is not None}
            if filtered:
                separator = "&" if urllib.parse.urlparse(full).query else "?"
                full = f"{full}{separator}{urllib.parse.urlencode(filtered)}"
        return full

    @staticmethod
    def _encode_body(
        json: Any, data: bytes | str | Mapping[str, Any] | None
    ) -> tuple[bytes | None, str | None]:
        """Serialise the request body and infer its content type."""
        if json is not None:
            return jsonlib.dumps(json).encode("utf-8"), "application/json"
        if data is None:
            return None, None
        if isinstance(data, bytes):
            return data, None
        if isinstance(data, str):
            return data.encode("utf-8"), "text/plain; charset=utf-8"
        return (
            urllib.parse.urlencode(dict(data)).encode("utf-8"),
            "application/x-www-form-urlencoded",
        )

    def _merge_headers(
        self, headers: Mapping[str, str] | None, content_type: str | None
    ) -> dict[str, str]:
        """Combine defaults, per-request headers and the inferred content type."""
        merged = {"User-Agent": self.user_agent, "Accept": "*/*"}
        merged.update(self.headers)
        if content_type:
            merged["Content-Type"] = content_type
        if headers:
            merged.update(headers)
        return merged

    def _sleep(self, attempt: int) -> None:
        """Exponential backoff between retries."""
        if self.backoff > 0:
            time.sleep(self.backoff * (2 ** (attempt - 1)))
