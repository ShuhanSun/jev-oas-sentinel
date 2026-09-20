import json
from io import BytesIO
import unittest
from unittest.mock import MagicMock, Mock, patch
from urllib.error import HTTPError

from jev_oas_sentinel.jev import JevClient, _ssl_context


class JevClientTest(unittest.TestCase):
    @patch("jev_oas_sentinel.jev.time.sleep")
    @patch("jev_oas_sentinel.jev.urlopen")
    def test_retry_metrics_include_failed_http_attempt(self, urlopen: Mock, sleep: Mock) -> None:
        failed = HTTPError(
            "https://example.test/jev", 500, "server error",
            {"Retry-After": "0"}, BytesIO(b'{"error":"temporary"}'),
        )
        response = Mock()
        response.status = 200
        response.read.return_value = json.dumps({
            "model": "resolved-model",
            "answers": {
                "change_kind": {
                    "type": "choice", "choice": "docs_only", "confidence": 1.0,
                    "probabilities": {"docs_only": 1.0},
                },
                "affected_dimension": {
                    "type": "choice", "choice": "none", "confidence": 1.0,
                    "probabilities": {"none": 1.0},
                },
                "old_promise_preserved": {"type": "noul", "noul": 1.0},
                "migration_burden": {
                    "type": "score", "score": 0, "confidence": 1.0,
                    "probabilities": {"0": 1.0},
                },
            },
        }).encode()
        success = MagicMock()
        success.__enter__.return_value = response
        urlopen.side_effect = [failed, success]
        events: list[dict[str, object]] = []
        client = JevClient("top-secret-key", trace=events.append, timeout=12.5, max_retries=1)

        client.evaluate({"operation": "GET /orders"})

        self.assertEqual(2, client.transport_metrics.attempts)
        self.assertEqual(1, client.transport_metrics.successes)
        self.assertEqual(1, client.transport_metrics.failures)
        self.assertEqual(1, client.transport_metrics.retries)
        self.assertTrue(events[0]["will_retry"])
        self.assertEqual(12.5, urlopen.call_args.kwargs["timeout"])
        sleep.assert_called_once_with(0.0)

    @patch("jev_oas_sentinel.jev.urlopen")
    def test_trace_records_io_without_api_key(self, urlopen: Mock) -> None:
        api_key = "top-secret-key"
        response = Mock()
        response.status = 200
        response.read.return_value = json.dumps({
            "model": "resolved-model",
            "echoed_authorization": f"Bearer {api_key}",
            "debug": {"Authorization": f"Bearer {api_key}"},
            "answers": {
                "change_kind": {
                    "type": "choice", "choice": "breaking", "confidence": .94,
                    "probabilities": {"breaking": .95},
                },
                "affected_dimension": {
                    "type": "choice", "choice": "default_behavior", "confidence": .98,
                    "probabilities": {"default_behavior": 1.0},
                },
                "old_promise_preserved": {"type": "noul", "noul": .03},
                "migration_burden": {
                    "type": "score", "score": 1.8, "confidence": .8,
                    "probabilities": {"2": .8},
                },
            },
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }).encode()
        urlopen.return_value.__enter__.return_value = response
        events: list[dict[str, object]] = []
        client = JevClient(api_key, trace=events.append)

        client.evaluate({"operation": "GET /orders"})

        self.assertEqual(1, len(events))
        self.assertEqual("GET /orders", events[0]["request"]["state"]["operation"])
        self.assertEqual("resolved-model", events[0]["response"]["model"])
        self.assertEqual("Bearer [REDACTED]", events[0]["response"]["echoed_authorization"])
        self.assertEqual("[REDACTED]", events[0]["response"]["debug"]["Authorization"])
        self.assertNotIn(api_key, json.dumps(events))
        self.assertEqual(1, client.transport_metrics.attempts)
        self.assertEqual(1, client.transport_metrics.successes)
        self.assertEqual(0, client.transport_metrics.failures)

    @patch("jev_oas_sentinel.jev.ssl.create_default_context")
    def test_explicit_ca_bundle_overrides_native_store(self, create_default_context: Mock) -> None:
        expected = Mock()
        create_default_context.return_value = expected

        actual = _ssl_context("/etc/company-ca.pem")

        self.assertIs(expected, actual)
        create_default_context.assert_called_once_with(cafile="/etc/company-ca.pem")

    @patch("jev_oas_sentinel.jev.truststore")
    def test_native_store_is_used_when_available(self, native_truststore: Mock) -> None:
        expected = Mock()
        native_truststore.SSLContext.return_value = expected

        actual = _ssl_context(None)

        self.assertIs(expected, actual)
        native_truststore.SSLContext.assert_called_once()

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
