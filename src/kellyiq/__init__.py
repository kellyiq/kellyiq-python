"""KellyIQ: size a whole sports betting slate as one portfolio.

A small client for the KellyIQ API (https://www.kellyiq.com/developers). No dependencies.

    from kellyiq import KellyIQ

    client = KellyIQ()          # reads KELLYIQ_API_KEY
    result = client.optimize({
        "bankroll": 1000,
        "picks": [
            {"sport": "baseball_mlb", "team": "Dodgers", "opponent": "Padres",
             "odds": -145, "opponentOdds": 125, "confidence": "MODERATE_EDGE"},
        ],
    })
    for stake in result["allocation"]["stakes"]:
        print(stake["team"], stake["stake"])

KellyIQ sizes the bets you choose; it does not choose bets or predict outcomes. Results are
calculations, not betting advice.
"""

from ._client import KellyIQ
from ._errors import (
    APIConnectionError,
    AuthenticationError,
    BadRequestError,
    BurstLimitError,
    DailyLimitError,
    KellyIQError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServerError,
    ServiceBusyError,
    SlateNotOptimizableError,
    UpgradeRequiredError,
    ValidationError,
)
from ._version import __version__

__all__ = [
    "KellyIQ",
    "KellyIQError",
    "APIConnectionError",
    "AuthenticationError",
    "BadRequestError",
    "BurstLimitError",
    "DailyLimitError",
    "NotFoundError",
    "PermissionDeniedError",
    "RateLimitError",
    "ServerError",
    "ServiceBusyError",
    "SlateNotOptimizableError",
    "UpgradeRequiredError",
    "ValidationError",
    "__version__",
]
