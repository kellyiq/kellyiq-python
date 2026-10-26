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
describes every field. Errors raise `KellyIQError` with `status`, `code`, `violations`, `request_id`
and `retry_after`.

This is an early release. A fuller SDK (typed results, automatic retries) is on the way; the
methods above will keep working.

## More

- [Quickstart](https://www.kellyiq.com/developers/quickstart) and [docs](https://www.kellyiq.com/developers)
- [Examples and AI-assistant (MCP) configs](https://github.com/kellyiq/kellyiq-examples)
- Support: support@kellyiq.com

KellyIQ sizes the bets you choose; it does not choose bets or predict outcomes. Results are
calculations, not betting advice. 21+, where legal.

MIT licensed.
