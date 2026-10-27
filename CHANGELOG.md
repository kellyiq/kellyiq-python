# Changelog

## 0.1.0

- A specific exception for each kind of error (`ValidationError`, `UpgradeRequiredError`,
  `DailyLimitError` and so on), all subclasses of `KellyIQError`, so existing `except KellyIQError`
  code keeps working. New fields: `required_tier`, `resets_at`.
- Automatic retries for `SERVICE_BUSY` and `BURST_LIMIT_EXCEEDED` (never counted against the
  allowance), and for dropped connections on `GET` calls. Settings: `max_retries`, `max_retry_wait`.
- `APIConnectionError` when no response arrives; `ServerError` (`INVALID_RESPONSE`) when something
  other than the API answers.
- The `User-Agent` now reports the real package version (0.0.2 sent `0.0.1`).
- Type information is shipped (`py.typed`).

## 0.0.2

- The example sends a confidence level every plan can use.

## 0.0.1

- First release: `optimize`, `sports`, `me`, `devig`, `implied_probability`, `kelly`.
