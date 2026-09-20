from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

import yaml


class OpenApiLoader:
    """Load OpenAPI JSON/YAML and resolve local JSON References safely."""

    def __init__(self, allowed_root: Path | None = None) -> None:
        self._documents: dict[Path, Any] = {}
        self._allowed_root = allowed_root.resolve() if allowed_root else None

    def load(self, path: Path) -> dict[str, Any]:
        source = path.resolve()
        if self._allowed_root is None:
            self._allowed_root = source.parent
        self._ensure_allowed(source)
        parsed = self._document(source)
        if not isinstance(parsed, dict):
            raise ValueError(f"OpenAPI document must be a top-level object: {path}")
        if not isinstance(parsed.get("openapi"), str) or not isinstance(parsed.get("paths"), dict):
            raise ValueError(f"Missing required OpenAPI fields 'openapi' or 'paths': {path}")
        resolved = self._resolve(parsed, source, frozenset())
        if not isinstance(resolved, dict):
            raise ValueError(f"Resolved OpenAPI document must be an object: {path}")
        return resolved

    def _document(self, path: Path) -> Any:
        cached = self._documents.get(path)
        if cached is not None:
            return cached
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"Cannot read OpenAPI reference {path}: {exc}") from exc
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ValueError(f"Cannot parse {path}: {exc}") from exc
        normalized = _json_value(parsed, set())
        self._documents[path] = normalized
        return normalized

    def _resolve(
        self,
        value: Any,
        source: Path,
        stack: frozenset[tuple[Path, str]],
    ) -> Any:
        if isinstance(value, dict):
            reference = value.get("$ref")
            if reference is not None:
                if not isinstance(reference, str) or not reference:
                    raise ValueError(f"$ref must be a non-empty string in {source}")
                resolved = self._reference(reference, source, stack)
                siblings = {
                    key: self._resolve(item, source, stack)
                    for key, item in value.items()
                    if key != "$ref"
                }
                if siblings:
                    if not isinstance(resolved, dict):
                        raise ValueError(f"$ref with sibling fields must resolve to an object: {reference}")
                    return {**resolved, **siblings}
                return resolved
            return {key: self._resolve(item, source, stack) for key, item in value.items()}
        if isinstance(value, list):
            return [self._resolve(item, source, stack) for item in value]
        return value

    def _reference(
        self,
        reference: str,
        source: Path,
        stack: frozenset[tuple[Path, str]],
    ) -> Any:
        parsed = urlsplit(reference)
        if parsed.scheme or parsed.netloc or parsed.query:
            raise ValueError(f"Remote or non-file $ref is disabled: {reference}")
        target = source if not parsed.path else (source.parent / unquote(parsed.path)).resolve()
        self._ensure_allowed(target)
        key = (target, parsed.fragment)
        if key in stack:
            return {"$ref": reference}
        document = self._document(target)
        selected = _json_pointer(document, parsed.fragment, reference)
        return self._resolve(selected, target, stack | {key})

    def _ensure_allowed(self, path: Path) -> None:
        assert self._allowed_root is not None
        try:
            path.relative_to(self._allowed_root)
        except ValueError as exc:
            raise ValueError(
                f"Local $ref escapes allowed root {self._allowed_root}: {path}"
            ) from exc


def load_openapi(path: Path, allowed_root: Path | None = None) -> dict[str, Any]:
    return OpenApiLoader(allowed_root).load(path)


def _json_pointer(document: Any, fragment: str, reference: str) -> Any:
    if not fragment:
        return document
    if not fragment.startswith("/"):
        raise ValueError(f"$ref fragment must be a JSON Pointer: {reference}")
    current = document
    for raw_token in fragment[1:].split("/"):
        token = unquote(raw_token).replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if token not in current:
                raise ValueError(f"$ref target does not exist: {reference}")
            current = current[token]
        elif isinstance(current, list):
            try:
                current = current[int(token)]
            except (ValueError, IndexError) as exc:
                raise ValueError(f"$ref array target does not exist: {reference}") from exc
        else:
            raise ValueError(f"$ref traverses a non-container value: {reference}")
    return current


def _json_value(value: Any, stack: set[int]) -> Any:
    if isinstance(value, dict):
        identity = id(value)
        if identity in stack:
            raise ValueError("Recursive YAML aliases are not supported")
        stack.add(identity)
        result: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = _json_key(key)
            if normalized_key in result:
                raise ValueError(f"Duplicate mapping key after YAML normalization: {normalized_key}")
            result[normalized_key] = _json_value(item, stack)
        stack.remove(identity)
        return result
    if isinstance(value, list):
        identity = id(value)
        if identity in stack:
            raise ValueError("Recursive YAML aliases are not supported")
        stack.add(identity)
        result = [_json_value(item, stack) for item in value]
        stack.remove(identity)
        return result
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError(f"Unsupported YAML value type: {type(value).__name__}")


def _json_key(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    raise ValueError(f"OpenAPI mapping keys must be scalar values, got {type(value).__name__}")
