import http.client
import json
import os
import socket
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional

from ._errors import APIConnectionError, BurstLimitError, KellyIQError, ServerError, ServiceBusyError, error_class

__all__ = ["KellyIQ", "KellyIQError"]   # KellyIQError stays importable from here, as in 0.0.x
from ._version import __version__

DEFAULT_BASE_URL = "https://api.kellyiq.com"


class KellyIQ:
    """Client for the KellyIQ API.

    :param api_key: your API key (``kiqa_...``); defaults to the ``KELLYIQ_API_KEY`` environment variable.
        Create one in the KellyIQ app under Settings, API. Every plan includes API access.
    :param base_url: defaults to ``KELLYIQ_API_BASE`` or https://api.kellyiq.com.
    :param timeout: seconds to wait for a response (an optimize can take several seconds).
    :param max_retries: how many times to retry when the API says it is busy (503 ``SERVICE_BUSY``)
        or too many requests arrived at once (429 ``BURST_LIMIT_EXCEEDED``). Neither counts against
        your allowance, so a retry is safe. ``0`` turns retries off.
    :param max_retry_wait: the longest wait, in seconds, the client will sleep for before a retry.
        When the API asks for longer, the error is raised instead.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None,
                 timeout: float = 60.0, max_retries: int = 2, max_retry_wait: float = 60.0) -> None:
        key = api_key or os.environ.get("KELLYIQ_API_KEY")
        if not key:
            raise ValueError("Pass api_key or set the KELLYIQ_API_KEY environment variable.")
        self._key = key
        self._base = (base_url or os.environ.get("KELLYIQ_API_BASE") or DEFAULT_BASE_URL).rstrip("/")
        self._timeout = timeout
        self._max_retries = max(0, max_retries)
        self._max_retry_wait = max(0.0, max_retry_wait)
        self._sleep: Callable[[float], None] = time.sleep

    def __repr__(self) -> str:   # never show the key
        return f"KellyIQ(base_url={self._base!r})"

    # ---- endpoints -------------------------------------------------------------------------

    def optimize(self, slate: Dict[str, Any]) -> Dict[str, Any]:
        """Size a slate (POST /v1/optimize). Returns the API response; stakes are in
        ``result["allocation"]["stakes"]``. Counts against your daily optimize allowance."""
        return self._request("POST", "/v1/optimize", slate)

    def sports(self) -> List[Dict[str, Any]]:
        """The sports you can size right now, with the key to send as each pick's ``sport``. Free."""
        return self._request("GET", "/v1/sports")["sports"]

    def me(self) -> Dict[str, Any]:
        """Your plan, today's allowance and the settings optimize applies by default. Free."""
        return self._request("GET", "/v1/me")

    def devig(self, markets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fair probabilities with the bookmaker's margin removed. Each market: ``{"odds": [-145, 125]}``."""
        return self._request("POST", "/v1/devig", {"markets": markets})["results"]

    def implied_probability(self, odds: List[int]) -> List[Dict[str, Any]]:
        """The probability each American price implies, margin included."""
        return self._request("POST", "/v1/implied-probability", {"odds": odds})["results"]

    def kelly(self, bets: List[Dict[str, Any]], bankroll: Optional[float] = None,
              fraction: Optional[float] = None) -> List[Dict[str, Any]]:
        """Kelly stake for each bet on its own. For two or more bets placed together, use optimize()."""
        body: Dict[str, Any] = {"bets": bets}
        if bankroll is not None:
            body["bankroll"] = bankroll
        if fraction is not None:
            body["fraction"] = fraction
        return self._request("POST", "/v1/kelly", body)["results"]

    # ---- transport -------------------------------------------------------------------------

    def _request(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Any:
        attempt = 0
        while True:
            try:
                return self._send(method, path, body)
            except (BurstLimitError, ServiceBusyError) as e:
                # Never counted against the allowance, so retrying cannot spend an optimize twice.
                wait = e.retry_after if e.retry_after is not None else 1
                if attempt >= self._max_retries or wait > self._max_retry_wait:
                    raise
            except APIConnectionError:
                # A POST that timed out may still have run (and counted), so only GETs are retried.
                if method != "GET" or attempt >= self._max_retries:
                    raise
                wait = 1
            attempt += 1
            self._sleep(wait)

    def _send(self, method: str, path: str, body: Optional[Dict[str, Any]]) -> Any:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self._base + path, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self._key}")
        req.add_header("Accept", "application/json")
        # Identifies SDK traffic, so KellyIQ can tell how many calls come through this package.
        req.add_header("User-Agent", f"kellyiq-python/{__version__}")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw_ok = resp.read().decode("utf-8", "replace")
                status_ok = resp.status
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            try:
                err = json.loads(raw)
            except ValueError:
                err = {}
            if not isinstance(err, dict):
                err = {}
            code = err.get("error") or f"HTTP_{e.code}"
            retry = e.headers.get("Retry-After") or str(err.get("retryAfterSeconds") or "")
            raise error_class(e.code, code)(
                status=e.code,
                code=code,
                message=err.get("message") or raw[:200] or str(e.reason),
                violations=err.get("violations"),
                request_id=err.get("requestId") or e.headers.get("X-Request-Id"),
                retry_after=int(retry) if retry.isdigit() else None,
                body=err,
            ) from None
        except (urllib.error.URLError, http.client.HTTPException, socket.timeout, TimeoutError, ConnectionError) as e:
            reason = getattr(e, "reason", None) or e
            raise APIConnectionError(None, "CONNECTION_ERROR", f"No response from {self._base}: {reason}") from e
        try:
            return json.loads(raw_ok)
        except ValueError:
            # A proxy or gateway answered instead of the API.
            raise ServerError(status_ok, "INVALID_RESPONSE", f"Expected JSON, got: {raw_ok[:200]}") from None
