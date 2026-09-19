from __future__ import annotations

import unittest

from jev_oas_sentinel.openapi import OpenApiDiffer


def spec(operation: dict, path_parameters: list | None = None) -> dict:
    path_item = {"get": operation}
    if path_parameters is not None:
        path_item["parameters"] = path_parameters
    return {"openapi": "3.0.3", "paths": {"/orders": path_item}}


class OpenApiDifferTest(unittest.TestCase):
    def test_detects_required_parameter(self) -> None:
        old = spec({"responses": {"200": {"description": "ok"}}})
        new = spec({
            "parameters": [{"name": "tenant", "in": "header", "required": True}],
            "responses": {"200": {"description": "ok"}},
        })
        issues = OpenApiDiffer().compare(old, new)[0].structural_issues
        self.assertIn("required-parameter-added", {issue.rule_id for issue in issues})

    def test_detects_description_only_change(self) -> None:
        changes = OpenApiDiffer().compare(
            spec({"description": "returns all", "responses": {"200": {"description": "ok"}}}),
            spec({"description": "returns active", "responses": {"200": {"description": "ok"}}}),
        )
        self.assertEqual(1, len(changes))
        self.assertTrue(changes[0].semantic_changed)
        self.assertEqual((), changes[0].structural_issues)

    def test_inherits_path_parameters(self) -> None:
        parameter = {"name": "tenant", "in": "header", "required": False}
        old = spec({"responses": {}}, [parameter])
        new = spec({"responses": {}}, [{**parameter, "required": True}])
        issues = OpenApiDiffer().compare(old, new)[0].structural_issues
        self.assertIn("parameter-became-required", {issue.rule_id for issue in issues})


if __name__ == "__main__":
    unittest.main()
