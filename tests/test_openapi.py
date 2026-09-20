from __future__ import annotations

import unittest

from jev_oas_sentinel.openapi import OpenApiDiffer


def spec(operation: dict, path_parameters: list | None = None) -> dict:
    path_item = {"get": operation}
    if path_parameters is not None:
        path_item["parameters"] = path_parameters
    return {"openapi": "3.0.3", "paths": {"/orders": path_item}}


class OpenApiDifferTest(unittest.TestCase):
    def test_detects_required_request_property_added(self) -> None:
        old = spec({
            "requestBody": {"content": {"application/json": {"schema": {
                "type": "object", "properties": {"name": {"type": "string"}},
            }}}},
            "responses": {},
        })
        new = spec({
            "requestBody": {"content": {"application/json": {"schema": {
                "type": "object", "properties": {"name": {"type": "string"}},
                "required": ["name"],
            }}}},
            "responses": {},
        })

        issues = OpenApiDiffer().compare(old, new)[0].structural_issues

        self.assertIn("request-required-property-added", {issue.rule_id for issue in issues})

    def test_detects_response_property_removed(self) -> None:
        old = spec({"responses": {"200": {"content": {"application/json": {"schema": {
            "type": "object", "properties": {"id": {"type": "string"}},
        }}}}}})
        new = spec({"responses": {"200": {"content": {"application/json": {"schema": {
            "type": "object", "properties": {},
        }}}}}})

        issues = OpenApiDiffer().compare(old, new)[0].structural_issues

        self.assertIn("response-property-removed", {issue.rule_id for issue in issues})

    def test_detects_response_enum_expansion(self) -> None:
        old = spec({"responses": {"200": {"content": {"application/json": {"schema": {
            "type": "string", "enum": ["active"],
        }}}}}})
        new = spec({"responses": {"200": {"content": {"application/json": {"schema": {
            "type": "string", "enum": ["active", "archived"],
        }}}}}})

        issues = OpenApiDiffer().compare(old, new)[0].structural_issues

        self.assertIn("response-enum-expanded", {issue.rule_id for issue in issues})

    def test_detects_response_media_type_removed(self) -> None:
        old = spec({"responses": {"200": {"content": {
            "application/json": {"schema": {"type": "object"}},
            "application/xml": {"schema": {"type": "object"}},
        }}}})
        new = spec({"responses": {"200": {"content": {
            "application/json": {"schema": {"type": "object"}},
        }}}})

        issues = OpenApiDiffer().compare(old, new)[0].structural_issues

        self.assertIn("response-media-type-removed", {issue.rule_id for issue in issues})

    def test_allows_request_type_expansion_but_blocks_response_type_expansion(self) -> None:
        old_request = spec({
            "requestBody": {"content": {"application/json": {"schema": {"type": "string"}}}},
            "responses": {},
        })
        new_request = spec({
            "requestBody": {"content": {"application/json": {"schema": {"type": ["string", "null"]}}}},
            "responses": {},
        })
        request_rules = {
            issue.rule_id for issue in OpenApiDiffer().compare(old_request, new_request)[0].structural_issues
        }
        self.assertNotIn("request-schema-type-incompatible", request_rules)

        old_response = spec({"responses": {"200": {"content": {"application/json": {
            "schema": {"type": "string"},
        }}}}})
        new_response = spec({"responses": {"200": {"content": {"application/json": {
            "schema": {"type": ["string", "null"]},
        }}}}})
        response_rules = {
            issue.rule_id for issue in OpenApiDiffer().compare(old_response, new_response)[0].structural_issues
        }
        self.assertIn("response-schema-type-incompatible", response_rules)

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
