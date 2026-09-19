"""A deliberately small YAML reader for conventional OpenAPI documents.

Unsupported YAML features fail loudly instead of being guessed. JSON syntax is
accepted for inline collections because JSON is a YAML subset.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any


@dataclass(frozen=True)
class _Line:
    number: int
    indent: int
    content: str
    raw: str


class YamlError(ValueError):
    pass


def parse(text: str) -> Any:
    return _Parser(text).parse()


class _Parser:
    def __init__(self, text: str) -> None:
        self.lines = self._tokenize(text)
        self.index = 0

    def parse(self) -> Any:
        if not self.lines:
            return {}
        result = self._node(self.lines[0].indent)
        if self.index != len(self.lines):
            self._fail(self.lines[self.index], "Unexpected indentation")
        return result

    def _node(self, indent: int) -> Any:
        line = self._current()
        if line.indent != indent:
            self._fail(line, f"Expected indentation {indent} but found {line.indent}")
        return self._sequence(indent) if line.content.startswith("-") else self._mapping(indent)

    def _mapping(self, indent: int) -> dict[str, Any]:
        result: dict[str, Any] = {}
        while self.index < len(self.lines):
            line = self._current()
            if line.indent < indent:
                break
            if line.indent > indent:
                self._fail(line, "Unexpected nested value")
            if line.content.startswith("-"):
                break
            key, raw_value = self._split_pair(line.content, line)
            self._reject_unsupported(key, raw_value, line)
            self.index += 1
            value = self._read_value(raw_value, indent, line)
            if key in result:
                self._fail(line, f"Duplicate key: {key}")
            result[key] = value
        return result

    def _sequence(self, indent: int) -> list[Any]:
        result: list[Any] = []
        while self.index < len(self.lines):
            line = self._current()
            if line.indent != indent or not line.content.startswith("-"):
                break
            item = line.content[1:].lstrip()
            self.index += 1
            if not item:
                result.append(self._node(self._current().indent) if self._nested(indent) else None)
                continue
            colon = self._mapping_colon(item)
            if colon < 0:
                result.append(self._scalar(item, line))
                if self._nested(indent):
                    self._fail(self._current(), "A scalar sequence item cannot have nested fields")
                continue
            key = self._key(item[:colon].strip(), line)
            raw_value = item[colon + 1 :].strip()
            self._reject_unsupported(key, raw_value, line)
            map_item = {key: self._read_value(raw_value, indent, line)}
            if self._nested(indent):
                continuation = self._node(self._current().indent)
                if not isinstance(continuation, dict):
                    self._fail(line, "A mapping sequence item must continue with mapping fields")
                overlap = map_item.keys() & continuation.keys()
                if overlap:
                    self._fail(line, f"Duplicate key: {next(iter(overlap))}")
                map_item.update(continuation)
            result.append(map_item)
        return result

    def _read_value(self, raw: str, parent_indent: int, source: _Line) -> Any:
        if not raw:
            return self._node(self._current().indent) if self._nested(parent_indent) else {}
        if re.fullmatch(r"[|>][-+]?[1-9]?", raw):
            return self._block(parent_indent, raw[0])
        return self._scalar(raw, source)

    def _block(self, parent_indent: int, style: str) -> str:
        if not self._nested(parent_indent):
            return ""
        content_indent = self._current().indent
        parts: list[str] = []
        while self.index < len(self.lines) and self._current().indent > parent_indent:
            line = self._current()
            if line.indent < content_indent:
                break
            parts.append(line.raw[content_indent:])
            self.index += 1
        return (" " if style == ">" else "\n").join(parts)

    def _scalar(self, raw: str, line: _Line) -> Any:
        value = self._strip_comment(raw).strip()
        if not value:
            return ""
        if (value.startswith("{") and value.endswith("}")) or (
            value.startswith("[") and value.endswith("]")
        ):
            if "'" in value:
                self._fail(line, "Inline collections must use JSON double quotes")
            try:
                return json.loads(value)
            except json.JSONDecodeError as exc:
                self._fail(line, f"Invalid inline JSON: {exc.msg}")
        if value[0] in "\"'":
            return self._quoted(value, line)
        lowered = value.lower()
        if lowered in {"null", "~"}:
            return None
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if re.fullmatch(r"[-+]?\d+", value):
            return int(value)
        if re.fullmatch(r"[-+]?(?:\d+\.\d*|\d*\.\d+)(?:[eE][-+]?\d+)?", value):
            return float(value)
        return value

    def _quoted(self, value: str, line: _Line) -> str:
        quote = value[0]
        if len(value) < 2 or value[-1] != quote:
            self._fail(line, "Unterminated quoted scalar")
        if quote == "'":
            return value[1:-1].replace("''", "'")
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            self._fail(line, f"Invalid quoted scalar: {exc.msg}")
        if not isinstance(parsed, str):
            self._fail(line, "Quoted scalar must be a string")
        return parsed

    def _nested(self, parent_indent: int) -> bool:
        return self.index < len(self.lines) and self._current().indent > parent_indent

    def _current(self) -> _Line:
        return self.lines[self.index]

    @staticmethod
    def _tokenize(text: str) -> list[_Line]:
        result: list[_Line] = []
        for number, raw in enumerate(text.replace("\r\n", "\n").replace("\r", "\n").split("\n"), 1):
            if "\t" in raw:
                raise YamlError(f"YAML tabs are not supported at line {number}")
            indent = len(raw) - len(raw.lstrip(" "))
            content = raw[indent:]
            if not content.strip() or content.lstrip().startswith("#"):
                continue
            result.append(_Line(number, indent, content, raw))
        return result

    @classmethod
    def _split_pair(cls, content: str, line: _Line) -> tuple[str, str]:
        colon = cls._mapping_colon(content)
        if colon < 0:
            cls._fail(line, "Expected a mapping entry")
        return cls._key(content[:colon].strip(), line), content[colon + 1 :].strip()

    @classmethod
    def _key(cls, raw: str, line: _Line) -> str:
        if not raw:
            cls._fail(line, "Mapping key cannot be empty")
        if raw[0] in "\"'" and raw[-1:] == raw[0]:
            return _Parser("")._quoted(raw, line)
        return raw

    @staticmethod
    def _mapping_colon(text: str) -> int:
        single = double = False
        square = brace = 0
        for position, char in enumerate(text):
            if char == "'" and not double:
                single = not single
            elif char == '"' and not single and (position == 0 or text[position - 1] != "\\"):
                double = not double
            elif not single and not double:
                square += (char == "[") - (char == "]")
                brace += (char == "{") - (char == "}")
                if char == ":" and square == brace == 0 and (
                    position + 1 == len(text) or text[position + 1].isspace()
                ):
                    return position
        return -1

    @staticmethod
    def _strip_comment(text: str) -> str:
        single = double = False
        for position, char in enumerate(text):
            if char == "'" and not double:
                single = not single
            elif char == '"' and not single and (position == 0 or text[position - 1] != "\\"):
                double = not double
            elif char == "#" and not single and not double and (
                position == 0 or text[position - 1].isspace()
            ):
                return text[:position]
        return text

    @staticmethod
    def _reject_unsupported(key: str, value: str, line: _Line) -> None:
        if key == "<<" or value.startswith(("&", "*", "!")):
            _Parser._fail(line, "YAML anchors, aliases, merge keys, and custom tags are not supported")

    @staticmethod
    def _fail(line: _Line, message: str) -> None:
        raise YamlError(f"{message} at YAML line {line.number}")

