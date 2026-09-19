import unittest

from jev_oas_sentinel.yaml_lite import YamlError, parse


class YamlLiteTest(unittest.TestCase):
    def test_parses_openapi_shaped_yaml(self) -> None:
        document = parse("""openapi: 3.0.3
paths:
  /pets:
    get:
      description: |
        First line.
        Second line.
      parameters:
        - name: limit
          in: query
          required: false
""")
        operation = document["paths"]["/pets"]["get"]
        self.assertEqual("First line.\nSecond line.", operation["description"])
        self.assertFalse(operation["parameters"][0]["required"])

    def test_rejects_anchors(self) -> None:
        with self.assertRaises(YamlError):
            parse("value: &shared thing\n")


if __name__ == "__main__":
    unittest.main()

