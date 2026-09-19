from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from .yaml_lite import parse as parse_yaml


HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace", "query"}
DOCUMENTATION_KEYS = {"summary", "description", "example", "examples", "externalDocs", "title"}


@dataclass(frozen=True)
class StructuralIssue:
    rule_id: str
    severity: str
    operation: str
    message: str


@dataclass(frozen=True)
class OperationChange:
    operation: str
    old_operation: dict[str, Any]
    new_operation: dict[str, Any]
    structural_issues: tuple[StructuralIssue, ...] = field(default_factory=tuple)
    semantic_changed: bool = False
    added: bool = False
    removed: bool = False


def load_spec(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        parsed = json.loads(text) if text.lstrip().startswith(("{", "[")) else parse_yaml(text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Cannot parse {path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"OpenAPI document must be a top-level object: {path}")
    if not isinstance(parsed.get("openapi"), str) or not isinstance(parsed.get("paths"), dict):
        raise ValueError(f"Missing required OpenAPI fields 'openapi' or 'paths': {path}")
    return parsed


class OpenApiDiffer:
    def compare(self, base: dict[str, Any], head: dict[str, Any]) -> list[OperationChange]:
        old_operations = self._operations(base)
        new_operations = self._operations(head)
        names = list(old_operations) + [name for name in new_operations if name not in old_operations]
        changes: list[OperationChange] = []
        for name in names:
            old = old_operations.get(name)
            new = new_operations.get(name)
            if old is None:
                changes.append(OperationChange(
                    name, {}, new or {},
                    (StructuralIssue("operation-added", "notice", name, "Operation was added"),),
                    added=True,
                ))
                continue
            if new is None:
                changes.append(OperationChange(
                    name, old, {},
                    (StructuralIssue("operation-removed", "block", name, "Operation was removed"),),
                    removed=True,
                ))
                continue
            if old == new:
                continue
            issues = self._compare_structure(name, old, new)
            semantic_changed = self._documentation_view(old) != self._documentation_view(new)
            if semantic_changed or issues:
                changes.append(OperationChange(name, old, new, tuple(issues), semantic_changed))
        return changes

    def semantic_state(self, change: OperationChange) -> dict[str, Any]:
        return {
            "operation": change.operation,
            "old_contract": self._compact(change.old_operation),
            "new_contract": self._compact(change.new_operation),
            "deterministic_changes": [
                {"rule": issue.rule_id, "severity": issue.severity, "message": issue.message}
                for issue in change.structural_issues
            ],
        }

    def _compare_structure(
        self, operation: str, old: dict[str, Any], new: dict[str, Any]
    ) -> list[StructuralIssue]:
        issues: list[StructuralIssue] = []
        self._compare_parameters(operation, old, new, issues)
        self._compare_request_body(operation, old, new, issues)
        self._compare_responses(operation, old, new, issues)
        if old.get("security") != new.get("security"):
            issues.append(StructuralIssue(
                "security-requirements-changed", "review", operation,
                "Security requirements changed; verify existing credentials and scopes remain valid",
            ))
        if self._remove_documentation(old) != self._remove_documentation(new) and not issues:
            issues.append(StructuralIssue(
                "structural-change-unclassified", "review", operation,
                "Non-documentation contract structure changed and requires compatibility review",
            ))
        return issues

    def _compare_parameters(
        self, operation: str, old: dict[str, Any], new: dict[str, Any], issues: list[StructuralIssue]
    ) -> None:
        old_params = self._parameters(old.get("parameters"))
        new_params = self._parameters(new.get("parameters"))
        for key, previous in old_params.items():
            updated = new_params.get(key)
            if updated is None:
                issues.append(StructuralIssue("parameter-removed", "block", operation, f"Parameter removed: {key}"))
                continue
            if not previous.get("required") and updated.get("required") is True:
                issues.append(StructuralIssue(
                    "parameter-became-required", "block", operation,
                    f"Optional parameter became required: {key}",
                ))
            if self._remove_documentation(previous) != self._remove_documentation(updated):
                issues.append(StructuralIssue(
                    "parameter-structure-changed", "review", operation,
                    f"Parameter schema or constraints changed: {key}",
                ))
        for key, parameter in new_params.items():
            if key not in old_params and parameter.get("required") is True:
                issues.append(StructuralIssue(
                    "required-parameter-added", "block", operation,
                    f"New required parameter added: {key}",
                ))

    def _compare_request_body(
        self, operation: str, old: dict[str, Any], new: dict[str, Any], issues: list[StructuralIssue]
    ) -> None:
        old_body = self._mapping(old.get("requestBody"))
        new_body = self._mapping(new.get("requestBody"))
        if not old_body.get("required") and new_body.get("required") is True:
            issues.append(StructuralIssue(
                "request-body-became-required", "block", operation, "Request body became required"
            ))
        if (old_body or new_body) and self._remove_documentation(old_body) != self._remove_documentation(new_body):
            issues.append(StructuralIssue(
                "request-body-structure-changed", "review", operation,
                "Request body schema or constraints changed",
            ))

    def _compare_responses(
        self, operation: str, old: dict[str, Any], new: dict[str, Any], issues: list[StructuralIssue]
    ) -> None:
        old_responses = self._mapping(old.get("responses"))
        new_responses = self._mapping(new.get("responses"))
        for status in old_responses:
            if status not in new_responses:
                issues.append(StructuralIssue(
                    "response-removed", "block", operation, f"Response status removed: {status}"
                ))
        if self._remove_documentation(old_responses) != self._remove_documentation(new_responses):
            issues.append(StructuralIssue(
                "response-structure-changed", "review", operation,
                "Response schemas or constraints changed",
            ))

    def _operations(self, document: dict[str, Any]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        global_security = document.get("security")
        for path, raw_path_item in self._mapping(document.get("paths")).items():
            path_item = self._mapping(raw_path_item)
            inherited = path_item.get("parameters")
            for method, raw_operation in path_item.items():
                if method.lower() not in HTTP_METHODS:
                    continue
                operation = dict(self._mapping(raw_operation))
                operation["parameters"] = self._merge_parameters(inherited, operation.get("parameters"))
                if "security" not in operation and global_security is not None:
                    operation["security"] = global_security
                result[f"{method.upper()} {path}"] = operation
        return result

    def _merge_parameters(self, inherited: Any, declared: Any) -> list[Any]:
        merged: dict[str, Any] = {}
        for collection in (inherited, declared):
            if not isinstance(collection, list):
                continue
            for index, item in enumerate(collection):
                parameter = self._mapping(item)
                if "$ref" in parameter:
                    key = f"$ref:{parameter['$ref']}"
                elif "name" in parameter and "in" in parameter:
                    key = f"{parameter['in']}:{parameter['name']}"
                else:
                    key = f"anonymous:{len(merged) + index}"
                merged[key] = item
        return list(merged.values())

    def _parameters(self, value: Any) -> dict[str, dict[str, Any]]:
        if not isinstance(value, list):
            return {}
        return {
            f"{parameter.get('in', '<unknown>')}:{parameter.get('name', '<unnamed>')}": parameter
            for item in value
            if (parameter := self._mapping(item))
        }

    def _documentation_view(self, value: Any) -> Any:
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for key, item in value.items():
                nested = item if key in DOCUMENTATION_KEYS else self._documentation_view(item)
                if nested not in (None, {}, []):
                    result[key] = nested
            return result
        if isinstance(value, list):
            return [nested for item in value if (nested := self._documentation_view(item)) not in (None, {}, [])]
        return None

    def _remove_documentation(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: self._remove_documentation(item)
                for key, item in value.items()
                if key not in DOCUMENTATION_KEYS
            }
        if isinstance(value, list):
            return [self._remove_documentation(item) for item in value]
        return value

    def _compact(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: self._compact(item)
                for key, item in value.items()
                if not key.startswith("x-") and key not in {"callbacks", "servers"}
            }
        if isinstance(value, list):
            return [self._compact(item) for item in value[:100]]
        if isinstance(value, str) and len(value) > 4_000:
            return value[:4_000] + "…[truncated]"
        return value

    @staticmethod
    def _mapping(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

