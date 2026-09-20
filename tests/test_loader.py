from pathlib import Path
import tempfile
import unittest

from jev_oas_sentinel.loader import load_openapi


class OpenApiLoaderTest(unittest.TestCase):
    def test_parses_anchors_merge_keys_and_yaml_timestamps(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "openapi.yaml"
            path.write_text("""openapi: 3.1.0
info: {title: Anchors, version: 1.0.0}
defaults: &defaults
  description: Shared description
  x-release-date: 2026-09-20
paths:
  /pets:
    get:
      <<: *defaults
      responses:
        200: {description: ok}
""")

            document = load_openapi(path)

            operation = document["paths"]["/pets"]["get"]
            self.assertEqual("Shared description", operation["description"])
            self.assertEqual("2026-09-20", operation["x-release-date"])
            self.assertIn("200", operation["responses"])

    def test_resolves_internal_reference(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "openapi.yaml"
            path.write_text("""openapi: 3.0.3
info: {title: Internal, version: 1.0.0}
paths:
  /pets:
    get:
      parameters:
        - $ref: '#/components/parameters/Limit'
      responses: {'200': {description: ok}}
components:
  parameters:
    Limit:
      name: limit
      in: query
      required: false
      schema: {type: integer}
""")

            document = load_openapi(path)

            parameter = document["paths"]["/pets"]["get"]["parameters"][0]
            self.assertEqual("limit", parameter["name"])
            self.assertNotIn("$ref", parameter)

    def test_resolves_external_file_reference(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "parameters.yaml").write_text("""parameters:
  Tenant:
    name: tenant
    in: header
    required: true
    schema: {type: string}
""")
            path = root / "openapi.yaml"
            path.write_text("""openapi: 3.0.3
info: {title: External, version: 1.0.0}
paths:
  /orders:
    get:
      parameters:
        - $ref: './parameters.yaml#/parameters/Tenant'
      responses: {'200': {description: ok}}
""")

            document = load_openapi(path)

            parameter = document["paths"]["/orders"]["get"]["parameters"][0]
            self.assertEqual("tenant", parameter["name"])
            self.assertTrue(parameter["required"])

    def test_preserves_reference_at_cycle_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "openapi.yaml"
            path.write_text("""openapi: 3.1.0
info: {title: Recursive, version: 1.0.0}
paths:
  /nodes:
    get:
      responses:
        '200':
          description: ok
          content:
            application/json:
              schema: {$ref: '#/components/schemas/Node'}
components:
  schemas:
    Node:
      type: object
      properties:
        child: {$ref: '#/components/schemas/Node'}
""")

            document = load_openapi(path)

            schema = document["paths"]["/nodes"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
            self.assertEqual("object", schema["type"])
            self.assertEqual(
                "#/components/schemas/Node",
                schema["properties"]["child"]["$ref"],
            )

    def test_rejects_remote_reference(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "openapi.yaml"
            path.write_text("""openapi: 3.0.3
info: {title: Remote, version: 1.0.0}
paths:
  /pets:
    $ref: 'https://example.com/path-item.yaml'
""")

            with self.assertRaisesRegex(ValueError, "Remote or non-file"):
                load_openapi(path)

    def test_rejects_reference_outside_default_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec_directory = root / "api"
            spec_directory.mkdir()
            (root / "shared.yaml").write_text("parameters: {Limit: {name: limit, in: query}}")
            path = spec_directory / "openapi.yaml"
            path.write_text("""openapi: 3.0.3
info: {title: Escape, version: 1.0.0}
paths:
  /pets:
    get:
      parameters: [{$ref: '../shared.yaml#/parameters/Limit'}]
      responses: {'200': {description: ok}}
""")

            with self.assertRaisesRegex(ValueError, "escapes allowed root"):
                load_openapi(path)

            document = load_openapi(path, root)
            parameter = document["paths"]["/pets"]["get"]["parameters"][0]
            self.assertEqual("limit", parameter["name"])


if __name__ == "__main__":
    unittest.main()
