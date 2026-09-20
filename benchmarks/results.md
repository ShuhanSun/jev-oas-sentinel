# Semantic routing benchmark

These cases keep the OpenAPI structure stable while changing a consumer-facing promise in contract prose.
The benchmark verifies that the deterministic layer reports no definite structural break and that Sentinel routes each change to JEV semantic review.
It does not claim model accuracy and does not call JEV.

**Result: 11/11 cases routed as expected.**

| Case | Dimension | Operation | Structural findings | JEV review planned |
|---|---|---|---:|:---:|
| `pagination-default` | pagination | `GET /orders` | 0 | yes |
| `ordering-guarantee` | ordering | `GET /events` | 0 | yes |
| `retry-idempotency` | retry/idempotency | `POST /payments` | 0 | yes |
| `not-found-meaning` | error semantics | `GET /profiles/{id}` | 0 | yes |
| `timestamp-zone` | response meaning | `GET /reports` | 0 | yes |
| `authorization-behavior` | authorization | `GET /invoices` | 0 | yes |
| `empty-collection` | response meaning | `GET /recommendations` | 0 | yes |
| `rate-limit-window` | retry behavior | `GET /search` | 0 | yes |
| `currency-units` | response meaning | `GET /balances` | 0 | yes |
| `deprecation-timeline` | deprecation | `POST /legacy-export` | 0 | yes |
| `webhook-retry-guarantee` | retry behavior | `POST /webhooks` | 0 | yes |

## Why these changes matter

- **pagination-default**: Clients may silently process fewer records per request.
- **ordering-guarantee**: Clients that rely on stable ordering may display or process events incorrectly.
- **retry-idempotency**: Automatic retries may create duplicate payments.
- **not-found-meaning**: Clients can no longer distinguish absence from authorization policy.
- **timestamp-zone**: Existing timestamp parsing and comparison logic may shift values.
- **authorization-behavior**: Previously authorized callers may start receiving authorization failures.
- **empty-collection**: Clients expecting an iterable array may fail on a missing value.
- **rate-limit-window**: Fixed retry schedules may repeatedly retry before capacity is available.
- **currency-units**: Consumers may display or transfer values at the wrong magnitude.
- **deprecation-timeline**: The migration window is shortened by one year.
- **webhook-retry-guarantee**: Consumers may miss webhook events if they rely on the previous retry guarantee.
