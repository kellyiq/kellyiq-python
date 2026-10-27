# kellyiq

Size a whole sports betting slate as one portfolio, from Python.

A small client for the [KellyIQ API](https://www.kellyiq.com/developers): send your bankroll and the
bets you have chosen, with your view of each, and get back a stake for every bet, sized across the
slate together under per-bet and total-exposure limits. No dependencies.

```bash
pip install kellyiq
```

```python
from kellyiq import KellyIQ

client = KellyIQ()   # reads KELLYIQ_API_KEY

result = client.optimize({
    "bankroll": 1000,
    "picks": [
        {"sport": "baseball_mlb", "team": "Dodgers", "opponent": "Padres",
         "odds": -145, "opponentOdds": 125, "confidence": "MODERATE_EDGE"},
        {"sport": "baseball_mlb", "team": "Cubs", "opponent": "Cardinals",
         "odds": 120, "opponentOdds": -140, "confidence": "MODERATE_EDGE"},
    ],
})

for stake in result["allocation"]["stakes"]:
    print(f'{stake["team"]}: ${stake["stake"]}')
```

Create an API key in the KellyIQ app under **Settings → API**. Every plan includes API access, Free
included, each with its own daily allowance.

## What's in it

| Method | Endpoint | Counts against the allowance |
|---|---|---|
| `optimize(slate)` | `POST /v1/optimize` | Yes |
| `sports()` | `GET /v1/sports` | No |
| `me()` | `GET /v1/me` | No |
| `devig(markets)` | `POST /v1/devig` | No |
| `implied_probability(odds)` | `POST /v1/implied-probability` | No |
| `kelly(bets, bankroll=None, fraction=None)` | `POST /v1/kelly` | No |

Responses are the API's JSON as Python dicts; the [API reference](https://www.kellyiq.com/developers/reference/optimize)
describes every field.

## Errors

Every error is a `KellyIQError` with `status`, `code`, `message`, `violations`, `request_id`,
`retry_after`, `required_tier` and `resets_at`. Catch a subclass to handle one case:

| Exception | When |
|---|---|
| `ValidationError` | 400: the request has problems; `violations` lists every one (`"picks[2].odds: ..."`) |
| `AuthenticationError` | 401 `INVALID_API_KEY`: the key is wrong, revoked or missing |
| `UpgradeRequiredError` | 403: something sent needs a higher plan (`required_tier`), such as your own probabilities on Free |
| `PermissionDeniedError` | 403: anything else the key may not do, such as `API_NOT_ENABLED` (API access is off) |
| `SlateNotOptimizableError` | 422: the slate is valid but cannot be sized; `violations` says why |
| `DailyLimitError` | 429: today's optimizes are used up; try again after `resets_at` |
| `BurstLimitError` | 429: too many at once (retried for you) |
| `ServiceBusyError` | 503: server capacity, not your allowance (retried for you) |
| `ServerError` | 5xx: quote `request_id` to support@kellyiq.com |
| `APIConnectionError` | no response at all: network, DNS or timeout |

```python
from kellyiq import KellyIQ, DailyLimitError, ValidationError

try:
    result = client.optimize(slate)
except ValidationError as e:
    print("Fix:", e.violations)
except DailyLimitError as e:
    print("No optimizes left until", e.resets_at)
```

## Retries

`SERVICE_BUSY` and `BURST_LIMIT_EXCEEDED` never count against your allowance, so the client retries
them for you after the wait the API asks for: up to `max_retries` times (default 2), and only when
the wait is at most `max_retry_wait` seconds (default 60). A dropped connection is retried for the
free `GET` calls only, since an optimize that timed out may already have run and counted.
`DAILY_LIMIT_EXCEEDED` is never retried.

```python
client = KellyIQ(max_retries=0)   # handle every error yourself
```

## Examples

- [A notebook](https://github.com/kellyiq/kellyiq-examples/blob/main/python/size-a-slate.ipynb):
  stakes, the probabilities behind them, and the risk at each Kelly fraction, as tables
- [Spreadsheet to stakes](https://github.com/kellyiq/kellyiq-examples/blob/main/python/slate_from_csv.py):
  CSV in, CSV of stakes out

## More

- [Python SDK guide](https://www.kellyiq.com/developers/python), [quickstart](https://www.kellyiq.com/developers/quickstart) and [docs](https://www.kellyiq.com/developers)
- [Examples and AI-assistant (MCP) configs](https://github.com/kellyiq/kellyiq-examples)
- Support: support@kellyiq.com

KellyIQ sizes the bets you choose; it does not choose bets or predict outcomes. Results are
calculations, not betting advice. 21+, where legal.

MIT licensed.
