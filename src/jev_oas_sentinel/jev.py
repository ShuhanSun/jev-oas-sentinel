from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import ssl
import sys
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    import truststore
except ImportError:  # Python 3.9 uses OpenSSL's configured CA bundle instead.
    truststore = None


DEFAULT_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-1.13.0"


@dataclass(frozen=True)
class SemanticDecision:
    model: str
    change_kind: str
    change_kind_probabilities: dict[str, float]
    change_kind_confidence: float
    affected_dimension: str
    affected_dimension_probabilities: dict[str, float]
    affected_dimension_confidence: float
    old_promise_preserved_probability: float
    migration_burden: float
    migration_burden_probabilities: dict[str, float]
    migration_burden_confidence: float
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def breaking_probability(self) -> float:
        return self.change_kind_probabilities.get("breaking", 0.0)


@dataclass
class JevTransportMetrics:
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    retries: int = 0
    latency_ms: int = 0


def questions() -> dict[str, Any]:
    return {
        "change_kind": {
            "type": "choice",
            "instructions": (
                "Classify the consumer-visible compatibility impact of changing `old_contract` to "
                "`new_contract` for the named API operation. Treat descriptions, examples, defaults, "
                "ordering, pagination, retry behavior, authorization, and error meanings as contractual "
                "when they make a behavioral promise."
            ),
            "criteria": {
                "docs_only": "Wording changed, but every consumer-visible behavioral promise is preserved.",
                "additive": "Optional behavior or clarification was added without invalidating old assumptions.",
                "behavioral_nonbreaking": "Behavior changed, but conforming existing clients remain correct.",
                "breaking": "A correct old client could fail, see materially different results, lose access, or require a coordinated change.",
                "unclear": "The supplied fragments are insufficient or genuinely ambiguous.",
            },
        },
        "affected_dimension": {
            "type": "choice",
            "instructions": "Which single semantic dimension is most materially affected by the contract change?",
            "criteria": {
                "none": "No consumer-visible semantic dimension changed.",
                "request_precondition": "Accepted inputs, context, or preconditions changed.",
                "default_behavior": "Behavior when an input is omitted or defaulted changed.",
                "response_meaning": "Meaning or guarantees of returned data changed.",
                "ordering_pagination": "Ordering, cursors, pages, limits, or result-set semantics changed.",
                "retry_idempotency": "Retry safety, duplication, idempotency, or timeout behavior changed.",
                "authentication_authorization": "Authentication, authorization, identity, or scopes changed.",
                "deprecation_migration": "Deprecation timing or migration expectations changed.",
                "error_semantics": "Error codes, retryability, partial success, or failure meanings changed.",
                "other": "Another consumer-visible semantic dimension changed.",
            },
        },
        "old_promise_preserved": {
            "type": "noul",
            "instructions": "Does `new_contract` preserve every consumer-visible behavioral promise made by `old_contract`?",
            "criteria": {
                "true": "Every old promise still holds.",
                "false": "At least one old promise is narrowed, removed, contradicted, or conditional.",
            },
        },
        "migration_burden": {
            "type": "score",
            "instructions": "Rate the client migration burden caused by this contract change.",
            "criteria": [
                "No client action; behavior and guarantees are preserved.",
                "Optional client update; existing clients remain correct.",
                "Required client code or configuration update that can roll out independently.",
                "Coordinated rollout, version negotiation, or substantial redesign is required.",
            ],
        },
    }


class JevClient:
    def __init__(
        self,
        api_key: str,
        endpoint: str = DEFAULT_ENDPOINT,
        model: str = DEFAULT_MODEL,
        ca_bundle: str | Path | None = None,
        trace: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("API key cannot be blank")
        self.api_key = api_key.strip()
        self.endpoint = endpoint
        self.model = model
        self.ssl_context = _ssl_context(ca_bundle)
        self.trace = trace
        self.transport_metrics = JevTransportMetrics()

    def evaluate(self, state: dict[str, Any]) -> SemanticDecision:
        request_body = {"state": state, "model": self.model, "questions": questions()}
        payload = json.dumps(request_body).encode()
        for attempt in range(1, 5):
            started = time.monotonic()
            request = Request(
                self.endpoint,
                data=payload,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urlopen(  # noqa: S310 - configured API endpoint
                    request, timeout=30, context=self.ssl_context
                ) as response:
                    body = response.read().decode("utf-8")
                    try:
                        response_body = json.loads(body)
                    except json.JSONDecodeError as exc:
                        duration_ms = self._finish_attempt(started, succeeded=False)
                        self._record_trace(
                            request_body, attempt, duration_ms, getattr(response, "status", 200),
                            body, f"Invalid JSON response: {exc.msg}",
                        )
                        raise
                    duration_ms = self._finish_attempt(started, succeeded=True)
                    self._record_trace(
                        request_body, attempt, duration_ms,
                        getattr(response, "status", 200), response_body,
                    )
                    return self._parse(response_body)
            except HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                will_retry = attempt < 4 and (exc.code in {429, 529} or exc.code >= 500)
                duration_ms = self._finish_attempt(started, succeeded=False, retried=will_retry)
                self._record_trace(
                    request_body, attempt, duration_ms, exc.code, _json_or_text(body),
                    f"HTTP {exc.code}", will_retry,
                )
                if will_retry:
                    delay = self._retry_delay(exc.headers.get("Retry-After"), attempt)
                    print(f"JEV request returned HTTP {exc.code}; retrying in {delay:.1f}s", file=sys.stderr)
                    time.sleep(delay)
                    continue
                raise OSError(f"JEV request failed with HTTP {exc.code}: {self._safe_body(body)}") from exc
            except (URLError, TimeoutError) as exc:
                duration_ms = self._finish_attempt(started, succeeded=False)
                self._record_trace(request_body, attempt, duration_ms, error=str(exc))
                raise OSError(f"JEV request failed: {exc}") from exc
            except json.JSONDecodeError as exc:
                raise OSError(f"JEV request failed: {exc}") from exc
        raise OSError("JEV request exhausted retries")

    def _record_trace(
        self,
        request_body: dict[str, Any],
        attempt: int,
        duration_ms: int,
        status: int | None = None,
        response: Any = None,
        error: str | None = None,
        will_retry: bool = False,
    ) -> None:
        if self.trace is None:
            return
        event: dict[str, Any] = {
            "endpoint": self.endpoint,
            "attempt": attempt,
            "duration_ms": duration_ms,
            "request": request_body,
        }
        if status is not None:
            event["status"] = status
        if response is not None:
            event["response"] = response
        if error:
            event["error"] = error
        if will_retry:
            event["will_retry"] = True
        self.trace(event)

    def _finish_attempt(self, started: float, *, succeeded: bool, retried: bool = False) -> int:
        duration_ms = int((time.monotonic() - started) * 1000)
        self.transport_metrics.attempts += 1
        self.transport_metrics.latency_ms += duration_ms
        if succeeded:
            self.transport_metrics.successes += 1
        else:
            self.transport_metrics.failures += 1
        if retried:
            self.transport_metrics.retries += 1
        return duration_ms

    def _parse(self, root: Any) -> SemanticDecision:
        try:
            if not isinstance(root, dict) or not isinstance(root.get("answers"), dict):
                raise ValueError("root or answers is not an object")
            answers = root["answers"]
            kind = self._answer(answers, "change_kind", "choice")
            dimension = self._answer(answers, "affected_dimension", "choice")
            preserved = self._answer(answers, "old_promise_preserved", "noul")
            burden = self._answer(answers, "migration_burden", "score")
            usage = root.get("usage") if isinstance(root.get("usage"), dict) else {}
            return SemanticDecision(
                str(root.get("model", self.model)),
                self._string(kind, "choice"), self._probabilities(kind), self._number(kind, "confidence"),
                self._string(dimension, "choice"), self._probabilities(dimension), self._number(dimension, "confidence"),
                self._number(preserved, "noul"),
                self._number(burden, "score"), self._probabilities(burden), self._number(burden, "confidence"),
                int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise OSError(f"Malformed JEV response: {exc}") from exc

    @staticmethod
    def _answer(answers: dict[str, Any], answer_id: str, expected: str) -> dict[str, Any]:
        answer = answers.get(answer_id)
        if not isinstance(answer, dict) or answer.get("type") != expected:
            raise ValueError(f"answer {answer_id} must have type {expected}")
        return answer

    @staticmethod
    def _string(value: dict[str, Any], key: str) -> str:
        result = value.get(key)
        if not isinstance(result, str) or not result:
            raise ValueError(f"missing string field {key}")
        return result

    @staticmethod
    def _number(value: dict[str, Any], key: str) -> float:
        result = value.get(key)
        if not isinstance(result, (int, float)) or isinstance(result, bool):
            raise ValueError(f"missing numeric field {key}")
        return float(result)

    @classmethod
    def _probabilities(cls, value: dict[str, Any]) -> dict[str, float]:
        raw = value.get("probabilities")
        if not isinstance(raw, dict):
            raise ValueError("probabilities must be an object")
        return {str(key): cls._numeric_probability(item, str(key)) for key, item in raw.items()}

    @staticmethod
    def _numeric_probability(value: Any, key: str) -> float:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"probability {key} must be numeric")
        return float(value)

    @staticmethod
    def _retry_delay(header: str | None, attempt: int) -> float:
        try:
            return min(float(header or ""), 10.0)
        except ValueError:
            return min(0.5 * 2 ** (attempt - 1), 4.0)

    @staticmethod
    def _safe_body(body: str) -> str:
        normalized = " ".join(body.split())
        return normalized if len(normalized) <= 500 else normalized[:500] + "…"


def _ssl_context(ca_bundle: str | Path | None) -> ssl.SSLContext:
    if ca_bundle:
        return ssl.create_default_context(cafile=str(ca_bundle))
    if truststore is not None:
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    return ssl.create_default_context()


def _json_or_text(body: str) -> Any:
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return body
