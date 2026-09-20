from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .loader import load_openapi


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


def load_spec(path: Path, ref_root: Path | None = None) -> dict[str, Any]:
    return load_openapi(path, ref_root)


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
        initial_issue_count = len(issues)
        old_body = self._mapping(old.get("requestBody"))
        new_body = self._mapping(new.get("requestBody"))
        if not old_body.get("required") and new_body.get("required") is True:
            issues.append(StructuralIssue(
                "request-body-became-required", "block", operation, "Request body became required"
            ))
        self._compare_content(operation, old_body, new_body, issues, "request")
        if (
            (old_body or new_body)
            and self._remove_documentation(old_body) != self._remove_documentation(new_body)
            and len(issues) == initial_issue_count
        ):
            issues.append(StructuralIssue(
                "request-body-structure-changed", "review", operation,
                "Request body schema or constraints changed",
            ))

    def _compare_responses(
        self, operation: str, old: dict[str, Any], new: dict[str, Any], issues: list[StructuralIssue]
    ) -> None:
        initial_issue_count = len(issues)
        old_responses = self._mapping(old.get("responses"))
        new_responses = self._mapping(new.get("responses"))
        for status, old_response in old_responses.items():
            new_response = new_responses.get(status)
            if new_response is None:
                issues.append(StructuralIssue(
                    "response-removed", "block", operation, f"Response status removed: {status}"
                ))
                continue
            self._compare_content(
                operation,
                self._mapping(old_response),
                self._mapping(new_response),
                issues,
                "response",
                f"response {status}",
            )
        if (
            self._remove_documentation(old_responses) != self._remove_documentation(new_responses)
            and len(issues) == initial_issue_count
        ):
            issues.append(StructuralIssue(
                "response-structure-changed", "review", operation,
                "Response schemas or constraints changed",
            ))

    def _compare_content(
        self,
        operation: str,
        old_container: dict[str, Any],
        new_container: dict[str, Any],
        issues: list[StructuralIssue],
        direction: str,
        location: str = "request body",
    ) -> None:
        old_content = self._mapping(old_container.get("content"))
        new_content = self._mapping(new_container.get("content"))
        for media_type, old_media in old_content.items():
            new_media = new_content.get(media_type)
            if new_media is None:
                issues.append(StructuralIssue(
                    f"{direction}-media-type-removed", "block", operation,
                    f"{location.capitalize()} media type removed: {media_type}",
                ))
                continue
            self._compare_schema(
                operation,
                self._mapping(self._mapping(old_media).get("schema")),
                self._mapping(self._mapping(new_media).get("schema")),
                issues,
                direction,
                f"{location} {media_type}",
                set(),
            )

    def _compare_schema(
        self,
        operation: str,
        old: dict[str, Any],
        new: dict[str, Any],
        issues: list[StructuralIssue],
        direction: str,
        location: str,
        visited: set[tuple[int, int]],
    ) -> None:
        if not old or not new:
            return
        identity = (id(old), id(new))
        if identity in visited:
            return
        visited.add(identity)

        old_types = self._schema_types(old.get("type"))
        new_types = self._schema_types(new.get("type"))
        incompatible_types = (
            direction == "request" and not old_types.issubset(new_types)
        ) or (
            direction == "response" and not new_types.issubset(old_types)
        )
        if old_types and new_types and incompatible_types:
            issues.append(StructuralIssue(
                f"{direction}-schema-type-incompatible", "block", operation,
                f"{location.capitalize()} type changed incompatibly from "
                f"{sorted(old_types)} to {sorted(new_types)}",
            ))
            return

        old_properties = self._mapping(old.get("properties"))
        new_properties = self._mapping(new.get("properties"))
        for name in old_properties:
            if name not in new_properties:
                issues.append(StructuralIssue(
                    f"{direction}-property-removed", "block", operation,
                    f"{location.capitalize()} property removed: {name}",
                ))

        old_required = self._required_names(old.get("required"), location)
        new_required = self._required_names(new.get("required"), location)
        if direction == "request":
            for name in sorted(new_required - old_required):
                issues.append(StructuralIssue(
                    "request-required-property-added", "block", operation,
                    f"{location.capitalize()} property became required: {name}",
                ))
        else:
            for name in sorted(old_required - new_required):
                issues.append(StructuralIssue(
                    "response-required-property-relaxed", "block", operation,
                    f"{location.capitalize()} property is no longer guaranteed: {name}",
                ))

        old_enum = old.get("enum")
        new_enum = new.get("enum")
        if isinstance(old_enum, list) and isinstance(new_enum, list):
            if direction == "request" and any(value not in new_enum for value in old_enum):
                issues.append(StructuralIssue(
                    "request-enum-narrowed", "block", operation,
                    f"{location.capitalize()} no longer accepts every previous enum value",
                ))
            if direction == "response" and any(value not in old_enum for value in new_enum):
                issues.append(StructuralIssue(
                    "response-enum-expanded", "block", operation,
                    f"{location.capitalize()} may return a new enum value",
                ))

        if direction == "request" and old.get("nullable") is True and new.get("nullable") is not True:
            issues.append(StructuralIssue(
                "request-nullability-narrowed", "block", operation,
                f"{location.capitalize()} no longer accepts null",
            ))
        if direction == "response" and old.get("nullable") is not True and new.get("nullable") is True:
            issues.append(StructuralIssue(
                "response-nullability-expanded", "block", operation,
                f"{location.capitalize()} may now return null",
            ))

        for name in old_properties.keys() & new_properties.keys():
            self._compare_schema(
                operation,
                self._mapping(old_properties[name]),
                self._mapping(new_properties[name]),
                issues,
                direction,
                f"{location}.{name}",
                visited,
            )
        self._compare_schema(
            operation,
            self._mapping(old.get("items")),
            self._mapping(new.get("items")),
            issues,
            direction,
            f"{location} items",
            visited,
        )

    @staticmethod
    def _schema_types(value: Any) -> set[str]:
        if isinstance(value, str):
            return {value}
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return set(value)
        return set()

    @staticmethod
    def _required_names(value: Any, location: str) -> set[str]:
        if value is None:
            return set()
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"Schema required field must be a string list at {location}")
        return set(value)

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
