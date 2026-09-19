import unittest

from jev_oas_sentinel.jev import JevClient


class JevClientTest(unittest.TestCase):
    def test_parses_typed_response(self) -> None:
        client = JevClient("not-a-real-key", model="requested")
        decision = client._parse({
            "model": "resolved-model",
            "answers": {
                "change_kind": {
                    "type": "choice", "choice": "breaking", "confidence": .94,
                    "probabilities": {"breaking": .95, "docs_only": .05},
                },
                "affected_dimension": {
                    "type": "choice", "choice": "default_behavior", "confidence": .98,
                    "probabilities": {"default_behavior": 1.0},
                },
                "old_promise_preserved": {
                    "type": "noul", "noul": .03, "confidence": .97,
                    "probabilities": {"true": .03, "false": .97},
                },
                "migration_burden": {
                    "type": "score", "score": 1.8, "confidence": .8,
                    "probabilities": {"0": .0, "1": .2, "2": .8, "3": .0},
                },
            },
            "usage": {"input_tokens": 10, "output_tokens": 5},
        })
        self.assertEqual("resolved-model", decision.model)
        self.assertEqual(.95, decision.breaking_probability)
        self.assertEqual(.03, decision.old_promise_preserved_probability)
        self.assertEqual(15, decision.input_tokens + decision.output_tokens)


if __name__ == "__main__":
    unittest.main()
