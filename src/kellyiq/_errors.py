from typing import Any, Dict, List, Optional


class KellyIQError(Exception):
    """An error from the KellyIQ API, or a request that never got an answer.

    Attributes mirror the API's error body: ``status`` (HTTP status, ``None`` when no response
    arrived), ``code`` (for example ``VALIDATION_ERROR`` or ``DAILY_LIMIT_EXCEEDED``),
    ``violations`` (each as ``"field: problem"``), ``request_id`` (quote it to
    support@kellyiq.com), ``retry_after`` (seconds, when the API asks you to wait),
    ``required_tier`` (upgrades only), ``resets_at`` (daily limit only) and ``body`` (the whole
    error response).

    Catch a subclass to handle one case; catch ``KellyIQError`` to handle them all.
    """

    def __init__(self, status: Optional[int], code: str, message: str,
                 violations: Optional[List[str]] = None, request_id: Optional[str] = None,
                 retry_after: Optional[int] = None, body: Optional[Dict[str, Any]] = None) -> None:
        detail = f"{code}: {message}" + (f" ({'; '.join(violations)})" if violations else "")
        super().__init__(f"HTTP {status} {detail}" if status else detail)
        self.status = status
        self.code = code
        self.message = message
        self.violations = violations or []
        self.request_id = request_id
        self.retry_after = retry_after
        self.body = body or {}
        self.required_tier: Optional[str] = self.body.get("requiredTier")
        self.resets_at: Optional[str] = self.body.get("resetsAt")


class APIConnectionError(KellyIQError):
    """The request never got an answer: no network, DNS failure or a timeout."""


class BadRequestError(KellyIQError):
    """400: the request could not be used."""


class ValidationError(BadRequestError):
    """400 ``VALIDATION_ERROR`` or ``INVALID_JSON``: ``violations`` lists every problem found."""


class AuthenticationError(KellyIQError):
    """401 ``INVALID_API_KEY``: the key is wrong, revoked or missing. Create one under Settings, API."""


class PermissionDeniedError(KellyIQError):
    """403: the key is valid but may not do this, for example ``API_NOT_ENABLED`` (API access is off)."""


class UpgradeRequiredError(PermissionDeniedError):
    """403 ``UPGRADE_REQUIRED``: something in the request needs a higher plan (``required_tier``)."""


class NotFoundError(KellyIQError):
    """404: no such endpoint."""


class SlateNotOptimizableError(KellyIQError):
    """422 ``SLATE_NOT_OPTIMIZABLE``: the slate is valid but cannot be sized; ``violations`` says why."""


class RateLimitError(KellyIQError):
    """429: too many requests."""


class DailyLimitError(RateLimitError):
    """429 ``DAILY_LIMIT_EXCEEDED``: today's optimizes are used up. Try again after ``resets_at``, never in a loop."""


class BurstLimitError(RateLimitError):
    """429 ``BURST_LIMIT_EXCEEDED``: too many at once. Not counted against the allowance; retried automatically."""


class ServerError(KellyIQError):
    """5xx: a problem on KellyIQ's side. Quote ``request_id`` to support@kellyiq.com."""


class ServiceBusyError(ServerError):
    """503 ``SERVICE_BUSY``: server capacity, not your allowance. Not counted; retried automatically."""


_BY_CODE = {
    "VALIDATION_ERROR": ValidationError,
    "INVALID_JSON": ValidationError,
    "INVALID_API_KEY": AuthenticationError,
    "UPGRADE_REQUIRED": UpgradeRequiredError,
    "SLATE_NOT_OPTIMIZABLE": SlateNotOptimizableError,
    "DAILY_LIMIT_EXCEEDED": DailyLimitError,
    "BURST_LIMIT_EXCEEDED": BurstLimitError,
    "SERVICE_BUSY": ServiceBusyError,
}

# The code set is open (new codes may arrive within v1), so an unknown code falls back to its status.
_BY_STATUS = {
    400: BadRequestError,
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: NotFoundError,
    422: SlateNotOptimizableError,
    429: RateLimitError,
}


def error_class(status: int, code: str) -> type:
    if code in _BY_CODE:
        return _BY_CODE[code]
    if status in _BY_STATUS:
        return _BY_STATUS[status]
    return ServerError if status >= 500 else KellyIQError
