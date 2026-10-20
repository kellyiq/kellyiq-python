import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

DEFAULT_BASE_URL = "https://api.kellyiq.com"
_VERSION = "0.0.1"


class KellyIQError(Exception):
    """An error response from the KellyIQ API.

    Attributes mirror the API's error body: ``status`` (HTTP status), ``code`` (for example
    ``VALIDATION_ERROR`` or ``DAILY_LIMIT_EXCEEDED``), ``violations`` (which field was wrong, for
    validation errors), ``request_id`` (quote it to support@kellyiq.com) and ``retry_after``
    (seconds, when the API asks you to wait).
    """

    def __init__(self, status: int, code: str, message: str, violations: Optional[List[str]] = None,
                 request_id: Optional[str] = None, retry_after: Optional[int] = None,
                 body: Optional[Dict[str, Any]] = None) -> None:
        detail = f"{code}: {message}" + (f" ({'; '.join(violations)})" if violations else "")
        super().__init__(f"HTTP {status} {detail}")
        self.status = status
        self.code = code
        self.message = message
        self.violations = violations or []
        self.request_id = request_id
        self.retry_after = retry_after
        self.body = body or {}


class KellyIQ:
    """Client for the KellyIQ API.

    :param api_key: your API key (``kiqa_...``); defaults to the ``KELLYIQ_API_KEY`` environment variable.
        Create one in the KellyIQ app under Settings, API. Every plan includes API access.
    :param base_url: defaults to ``KELLYIQ_API_BASE`` or https://api.kellyiq.com.
    :param timeout: seconds to wait for a response (an optimize can take several seconds).
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None,
                 timeout: float = 60.0) -> None:
        key = api_key or os.environ.get("KELLYIQ_API_KEY")
        if not key:
            raise ValueError("Pass api_key or set the KELLYIQ_API_KEY environment variable.")
        self._key = key
        self._base = (base_url or os.environ.get("KELLYIQ_API_BASE") or DEFAULT_BASE_URL).rstrip("/")
        self._timeout = timeout

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

    def _request(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self._base + path, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self._key}")
        req.add_header("Accept", "application/json")
        # Identifies SDK traffic, so KellyIQ can tell how many calls come through this package.
        req.add_header("User-Agent", f"kellyiq-python/{_VERSION}")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            try:
                err = json.loads(raw)
            except ValueError:
                err = {}
            retry = e.headers.get("Retry-After")
            raise KellyIQError(
                status=e.code,
                code=err.get("error", f"HTTP_{e.code}"),
                message=err.get("message", raw[:200] or e.reason),
                violations=err.get("violations"),
                request_id=err.get("requestId") or e.headers.get("X-Request-Id"),
                retry_after=int(retry) if retry and retry.isdigit() else None,
                body=err,
            ) from None
