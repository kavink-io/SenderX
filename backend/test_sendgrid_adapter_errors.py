import unittest
from unittest.mock import Mock

from app.adapters.email.sendgrid_adapter import SendGridAdapter


class ProviderHTTPError(Exception):
    status_code = 403

    def __init__(self, body):
        self.body = body


class SendGridErrorHandlingTests(unittest.TestCase):
    def setUp(self):
        self.key = "unit-test-secret-key"
        self.adapter = SendGridAdapter(self.key, "verified@example.com")
        self.adapter.client = Mock()
        self.message = {
            "recipient": "recipient@example.com",
            "data": {"subject": "test", "message": "test"},
        }

    def test_captures_403_body_and_redacts_api_key(self):
        self.adapter.client.send.side_effect = ProviderHTTPError(
            f'{{"errors":[{{"message":"denied {self.key}"}}]}}'
        )

        with self.assertRaisesRegex(RuntimeError, "HTTP: 403") as raised:
            self.adapter.send(self.message)

        self.assertIn('"message":"denied [REDACTED]"', str(raised.exception))
        self.assertNotIn(self.key, str(raised.exception))

    def test_decodes_byte_response_body(self):
        self.adapter.client.send.side_effect = ProviderHTTPError(b'{"error":"forbidden"}')

        with self.assertRaises(RuntimeError) as raised:
            self.adapter.send(self.message)

        self.assertIn('{"error":"forbidden"}', str(raised.exception))


if __name__ == "__main__":
    unittest.main()
