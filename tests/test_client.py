"""Client tests against a local fake of the API: no network, no key, no allowance used."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import kellyiq
from kellyiq import (
    APIConnectionError,
    AuthenticationError,
    BurstLimitError,
    DailyLimitError,
    KellyIQ,
    KellyIQError,
    PermissionDeniedError,
    RateLimitError,
    ServerError,
    ServiceBusyError,
    SlateNotOptimizableError,
    UpgradeRequiredError,
    ValidationError,
)


class FakeAPI:
    """Answers each request with the next queued (status, body, headers); records what it got."""

    def __init__(self):
        self.replies = []
        self.requests = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def _answer(self):
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                fake.requests.append({
                    "method": self.command,
                    "path": self.path,
                    "headers": dict(self.headers),
                    "body": json.loads(raw) if raw else None,
                })
                status, body, headers = fake.replies.pop(0)
                payload = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(payload)

            do_GET = do_POST = _answer

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def reply(self, status, body, headers=None):
        self.replies.append((status, body, headers))


@pytest.fixture
def api():
    fake = FakeAPI()
    yield fake
    fake.server.shutdown()


def client_for(api, **kw):
    c = KellyIQ(api_key="kiqa_test", base_url=api.url, **kw)
    c.sleeps = []
    c._sleep = c.sleeps.append   # record waits instead of sleeping
    return c


def err(code, status_msg="nope", **extra):
    return {"error": code, "message": status_msg, "requestId": "req_1", **extra}


# ---- requests ---------------------------------------------------------------------------------

def test_optimize_sends_the_slate_with_key_and_user_agent(api):
    api.reply(200, {"allocation": {"stakes": [{"team": "Dodgers", "stake": 41.2}]}})
    slate = {"bankroll": 1000, "picks": [{"sport": "baseball_mlb", "team": "Dodgers", "opponent": "Padres",
                                          "odds": -145, "opponentOdds": 125, "confidence": "MODERATE_EDGE"}]}
    result = client_for(api).optimize(slate)

    assert result["allocation"]["stakes"][0]["stake"] == 41.2
    req = api.requests[0]
    assert (req["method"], req["path"], req["body"]) == ("POST", "/v1/optimize", slate)
    assert req["headers"]["Authorization"] == "Bearer kiqa_test"
    assert req["headers"]["User-Agent"] == f"kellyiq-python/{kellyiq.__version__}"


def test_free_endpoints_unwrap_their_lists(api):
    api.reply(200, {"sports": [{"key": "baseball_mlb", "name": "MLB"}]})
    api.reply(200, {"results": [{"fair": [0.57, 0.43]}]})
    api.reply(200, {"results": [{"probability": 0.59}]})
    api.reply(200, {"results": [{"stake": 12.0}]})
    api.reply(200, {"tier": "free"})
    c = client_for(api)

    assert c.sports() == [{"key": "baseball_mlb", "name": "MLB"}]
    assert c.devig([{"odds": [-145, 125]}]) == [{"fair": [0.57, 0.43]}]
    assert c.implied_probability([-145]) == [{"probability": 0.59}]
    assert c.kelly([{"odds": -110, "probability": 0.55}], bankroll=500, fraction=0.5) == [{"stake": 12.0}]
    assert c.me() == {"tier": "free"}
    assert [r["path"] for r in api.requests] == ["/v1/sports", "/v1/devig", "/v1/implied-probability",
                                                 "/v1/kelly", "/v1/me"]
    assert api.requests[3]["body"] == {"bets": [{"odds": -110, "probability": 0.55}], "bankroll": 500, "fraction": 0.5}


def test_key_from_environment_and_never_in_repr(api, monkeypatch):
    monkeypatch.setenv("KELLYIQ_API_KEY", "kiqa_env")
    c = KellyIQ(base_url=api.url)
    assert "kiqa_env" not in repr(c)
    api.reply(200, {"tier": "free"})
    c.me()
    assert api.requests[0]["headers"]["Authorization"] == "Bearer kiqa_env"


def test_missing_key_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("KELLYIQ_API_KEY", raising=False)
    with pytest.raises(ValueError, match="KELLYIQ_API_KEY"):
        KellyIQ()


# ---- typed errors -----------------------------------------------------------------------------

@pytest.mark.parametrize("status,code,cls", [
    (400, "VALIDATION_ERROR", ValidationError),
    (400, "INVALID_JSON", ValidationError),
    (401, "INVALID_API_KEY", AuthenticationError),
    (403, "API_NOT_ENABLED", PermissionDeniedError),
    (403, "UPGRADE_REQUIRED", UpgradeRequiredError),
    (403, "FORBIDDEN", PermissionDeniedError),
    (422, "SLATE_NOT_OPTIMIZABLE", SlateNotOptimizableError),
    (429, "DAILY_LIMIT_EXCEEDED", DailyLimitError),
    (500, "INTERNAL_ERROR", ServerError),
    (403, "SOME_NEW_CODE", PermissionDeniedError),   # unknown codes fall back to the status
    (418, "SOME_NEW_CODE", KellyIQError),
])
def test_each_error_code_raises_its_own_class(api, status, code, cls):
    api.reply(status, err(code))
    with pytest.raises(cls) as e:
        client_for(api).optimize({"bankroll": 100, "picks": []})
    assert type(e.value) is cls
    assert isinstance(e.value, KellyIQError)
    assert (e.value.status, e.value.code, e.value.request_id) == (status, code, "req_1")


def test_error_fields_are_carried(api):
    api.reply(403, err("UPGRADE_REQUIRED", violations=["picks[0].probability: needs Bettor"], requiredTier="bettor"))
    with pytest.raises(UpgradeRequiredError) as e:
        client_for(api).optimize({"bankroll": 100, "picks": []})
    assert e.value.violations == ["picks[0].probability: needs Bettor"]
    assert e.value.required_tier == "bettor"
    assert "needs Bettor" in str(e.value)


def test_daily_limit_is_never_retried(api):
    api.reply(429, err("DAILY_LIMIT_EXCEEDED", retryAfterSeconds=3600, resetsAt="2026-10-27T00:00:00Z"),
              {"Retry-After": "3600"})
    c = client_for(api)
    with pytest.raises(DailyLimitError) as e:
        c.optimize({"bankroll": 100, "picks": []})
    assert isinstance(e.value, RateLimitError)
    assert (e.value.retry_after, e.value.resets_at) == (3600, "2026-10-27T00:00:00Z")
    assert len(api.requests) == 1 and c.sleeps == []


def test_non_json_error_body_still_raises_by_status(api):
    api.reply(502, b"<html>Bad gateway</html>")
    with pytest.raises(ServerError) as e:
        client_for(api).me()
    assert e.value.code == "HTTP_502"
    assert "Bad gateway" in e.value.message


# ---- retries ----------------------------------------------------------------------------------

def test_busy_and_burst_are_retried_after_the_requested_wait(api):
    api.reply(503, err("SERVICE_BUSY"), {"Retry-After": "5"})
    api.reply(429, err("BURST_LIMIT_EXCEEDED", retryAfterSeconds=2), {"Retry-After": "2"})
    api.reply(200, {"allocation": {"stakes": []}})
    c = client_for(api)
    assert c.optimize({"bankroll": 100, "picks": []}) == {"allocation": {"stakes": []}}
    assert len(api.requests) == 3
    assert c.sleeps == [5, 2]


def test_retries_stop_at_max_retries(api):
    for _ in range(3):
        api.reply(503, err("SERVICE_BUSY"), {"Retry-After": "1"})
    c = client_for(api, max_retries=2)
    with pytest.raises(ServiceBusyError):
        c.optimize({"bankroll": 100, "picks": []})
    assert len(api.requests) == 3 and c.sleeps == [1, 1]


def test_retries_off(api):
    api.reply(429, err("BURST_LIMIT_EXCEEDED"), {"Retry-After": "1"})
    c = client_for(api, max_retries=0)
    with pytest.raises(BurstLimitError):
        c.optimize({"bankroll": 100, "picks": []})
    assert c.sleeps == []


def test_a_wait_longer_than_max_retry_wait_raises_instead(api):
    api.reply(429, err("BURST_LIMIT_EXCEEDED"), {"Retry-After": "90"})
    c = client_for(api, max_retry_wait=60)
    with pytest.raises(BurstLimitError) as e:
        c.optimize({"bankroll": 100, "picks": []})
    assert e.value.retry_after == 90 and c.sleeps == []


def test_retry_after_from_body_when_header_missing(api):
    api.reply(429, err("BURST_LIMIT_EXCEEDED", retryAfterSeconds=4))
    api.reply(200, {"ok": True})
    c = client_for(api)
    c.optimize({"bankroll": 100, "picks": []})
    assert c.sleeps == [4]


# ---- no response ------------------------------------------------------------------------------

def _dead_url():
    server = HTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    port = server.server_address[1]
    server.server_close()   # nothing listens here now
    return f"http://127.0.0.1:{port}"


def test_connection_failure_on_a_get_is_retried_then_raised():
    c = KellyIQ(api_key="kiqa_test", base_url=_dead_url())
    c.sleeps = []
    c._sleep = c.sleeps.append
    with pytest.raises(APIConnectionError) as e:
        c.me()
    assert e.value.status is None and e.value.code == "CONNECTION_ERROR"
    assert c.sleeps == [1, 1]


def test_connection_failure_on_optimize_is_not_retried():
    # The optimize may have run and counted before the connection dropped.
    c = KellyIQ(api_key="kiqa_test", base_url=_dead_url())
    c.sleeps = []
    c._sleep = c.sleeps.append
    with pytest.raises(APIConnectionError):
        c.optimize({"bankroll": 100, "picks": []})
    assert c.sleeps == []


def test_non_json_success_body_raises_server_error(api):
    api.reply(200, b"<html>captive portal</html>")
    with pytest.raises(ServerError) as e:
        client_for(api).me()
    assert e.value.code == "INVALID_RESPONSE"


def test_old_private_import_path_still_works():
    from kellyiq._client import KellyIQError as Old
    assert Old is KellyIQError
