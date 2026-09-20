from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

import yaml

from .policy import Finding


CONFIG_FILENAME = ".jev-sentinel.yaml"
_CONFIG_KEYS = {
    "version",
    "mode",
    "fail_on_review",
    "model",
    "review_threshold",
    "block_threshold",
    "max_jev_calls",
    "timeout",
    "max_retries",
    "suppressions",
}


@dataclass(frozen=True)
class Suppression:
    operation: str
    rule: str
    expires: date
    owner: str
    reason: str

    def matches(self, finding: Finding) -> bool:
        return fnmatchcase(finding.operation, self.operation) and fnmatchcase(finding.rule_id, self.rule)


@dataclass(frozen=True)
class SentinelConfig:
    path: Path | None = None
    mode: str | None = None
    fail_on_review: bool | None = None
    model: str | None = None
    review_threshold: float | None = None
    block_threshold: float | None = None
    max_jev_calls: int | None = None
    timeout: float | None = None
    max_retries: int | None = None
    suppressions: tuple[Suppression, ...] = ()


def discover_config(explicit: Path | None, disabled: bool) -> SentinelConfig:
    if disabled:
        return SentinelConfig()
    candidate = explicit or Path.cwd() / CONFIG_FILENAME
    if explicit is None and not candidate.is_file():
        return SentinelConfig()
    return load_config(candidate)


def load_config(path: Path) -> SentinelConfig:
    source = path.resolve()
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Cannot read configuration {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"Cannot parse configuration {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"Configuration must be a mapping: {path}")
    unknown = set(raw) - _CONFIG_KEYS
    if unknown:
        raise ValueError(f"Unknown configuration fields: {', '.join(sorted(map(str, unknown)))}")
    if raw.get("version") != 1:
        raise ValueError("Configuration version must be 1")

    mode = _optional_string(raw, "mode")
    if mode is not None and mode not in {"advisory", "enforce"}:
        raise ValueError("Configuration mode must be advisory or enforce")
    return SentinelConfig(
        path=source,
        mode=mode,
        fail_on_review=_optional_boolean(raw, "fail_on_review"),
        model=_optional_string(raw, "model"),
        review_threshold=_optional_probability(raw, "review_threshold"),
        block_threshold=_optional_probability(raw, "block_threshold"),
        max_jev_calls=_optional_integer(raw, "max_jev_calls", minimum=0),
        timeout=_optional_number(raw, "timeout", positive=True),
        max_retries=_optional_integer(raw, "max_retries", minimum=0),
        suppressions=_suppressions(raw.get("suppressions")),
    )


def apply_suppressions(
    findings: tuple[Finding, ...],
    suppressions: tuple[Suppression, ...],
    today: date | None = None,
) -> tuple[tuple[Finding, ...], int]:
    current_date = today or datetime.now(timezone.utc).date()
    validate_suppressions(suppressions, current_date)
    result: list[Finding] = []
    suppressed_count = 0
    for finding in findings:
        suppression = next(
            (
                item for item in suppressions
                if finding.severity in {"block", "review"} and item.matches(finding)
            ),
            None,
        )
        if suppression is None:
            result.append(finding)
            continue
        suppressed_count += 1
        evidence = dict(finding.evidence)
        evidence["suppression"] = {
            "operation": suppression.operation,
            "rule": suppression.rule,
            "expires": suppression.expires.isoformat(),
            "owner": suppression.owner,
            "reason": suppression.reason,
            "original_severity": finding.severity,
        }
        result.append(Finding(
            finding.rule_id,
            "notice",
            finding.operation,
            f"{finding.message} ({finding.severity} suppressed until "
            f"{suppression.expires.isoformat()} "
            f"by {suppression.owner}: {suppression.reason})",
            finding.source,
            evidence,
        ))
    return tuple(result), suppressed_count


def validate_suppressions(
    suppressions: tuple[Suppression, ...], today: date | None = None
) -> None:
    current_date = today or datetime.now(timezone.utc).date()
    expired = [item for item in suppressions if item.expires < current_date]
    if expired:
        item = expired[0]
        raise ValueError(
            f"Expired suppression for {item.operation} / {item.rule}: {item.expires.isoformat()}"
        )


def _suppressions(value: Any) -> tuple[Suppression, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError("Configuration suppressions must be a list")
    result: list[Suppression] = []
    expected = {"operation", "rule", "expires", "owner", "reason"}
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"Suppression {index + 1} must be a mapping")
        unknown = set(item) - expected
        missing = expected - set(item)
        if unknown or missing:
            detail = []
            if missing:
                detail.append(f"missing {', '.join(sorted(missing))}")
            if unknown:
                detail.append(f"unknown {', '.join(sorted(map(str, unknown)))}")
            raise ValueError(f"Invalid suppression {index + 1}: {'; '.join(detail)}")
        result.append(Suppression(
            _required_string(item, "operation", index),
            _required_string(item, "rule", index),
            _date(item["expires"], index),
            _required_string(item, "owner", index),
            _required_string(item, "reason", index),
        ))
    return tuple(result)


def _required_string(value: dict[str, Any], key: str, index: int) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"Suppression {index + 1} field {key} must be a non-empty string")
    return item.strip()


def _date(value: Any, index: int) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise ValueError(f"Suppression {index + 1} expires must be an ISO date")


def _optional_string(value: dict[str, Any], key: str) -> str | None:
    item = value.get(key)
    if item is None:
        return None
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"Configuration field {key} must be a non-empty string")
    return item.strip()


def _optional_boolean(value: dict[str, Any], key: str) -> bool | None:
    item = value.get(key)
    if item is None:
        return None
    if not isinstance(item, bool):
        raise ValueError(f"Configuration field {key} must be true or false")
    return item


def _optional_probability(value: dict[str, Any], key: str) -> float | None:
    item = _optional_number(value, key)
    if item is not None and not 0 <= item <= 1:
        raise ValueError(f"Configuration field {key} must be between 0 and 1")
    return item


def _optional_number(value: dict[str, Any], key: str, positive: bool = False) -> float | None:
    item = value.get(key)
    if item is None:
        return None
    if not isinstance(item, (int, float)) or isinstance(item, bool):
        raise ValueError(f"Configuration field {key} must be numeric")
    parsed = float(item)
    if positive and parsed <= 0:
        raise ValueError(f"Configuration field {key} must be greater than zero")
    return parsed


def _optional_integer(value: dict[str, Any], key: str, minimum: int) -> int | None:
    item = value.get(key)
    if item is None:
        return None
    if not isinstance(item, int) or isinstance(item, bool) or item < minimum:
        raise ValueError(f"Configuration field {key} must be an integer >= {minimum}")
    return item
