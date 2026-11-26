"""Regression checks for production-sensitive WhatsApp adapter behavior."""

import pytest
import requests

from app.adapters.base_adapter import ProviderError
from app.adapters.whatsapp.cloud_adapter import WhatsAppCloudAdapter


class RedirectSession:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return RedirectResponse()


class RedirectResponse:
    status_code = 307
    text = "redirect"

    def json(self):
        raise ValueError("no JSON body")


class ErrorResponse:
    status_code = 400
    text = "sensitive customer address: 1 Main Street"
    headers = {"Retry-After": "23"}

    def json(self):
        return {"error": {"code": 131009, "message": self.text}}


class ErrorSession:
    def post(self, url, **kwargs):
        return ErrorResponse()


def test_cloud_send_does_not_follow_redirect_with_bearer_token():
    session = RedirectSession()
    adapter = WhatsAppCloudAdapter(
        access_token="mock-secret-access-token",
        phone_number_id="123456789012345",
        session=session,
    )
    with pytest.raises(ProviderError):
        adapter.send({"recipient": "+14155552671", "data": {"type": "text", "text": "hello"}})
    assert len(session.calls) == 1
    assert session.calls[0][1]["allow_redirects"] is False


def test_provider_error_text_does_not_expose_message_content(caplog):
    adapter = WhatsAppCloudAdapter(
        access_token="mock-secret-access-token",
        phone_number_id="123456789012345",
        session=ErrorSession(),
    )
    with pytest.raises(ProviderError) as error:
        adapter.send({"recipient": "+14155552671", "data": {"type": "text", "text": "private content"}})
    assert "1 Main Street" not in str(error.value)
    assert "1 Main Street" not in caplog.text


def test_retryable_meta_error_honors_retry_after_header():
    class RateLimitResponse(ErrorResponse):
        status_code = 429
        text = "Rate limit"
        headers = {"Retry-After": "23"}

        def json(self):
            return {"error": {"code": 130429, "message": self.text}}

    class RateLimitSession:
        def post(self, *args, **kwargs):
            return RateLimitResponse()

    adapter = WhatsAppCloudAdapter(
        access_token="mock-secret-access-token",
        phone_number_id="123456789012345",
        session=RateLimitSession(),
    )
    with pytest.raises(ProviderError) as error:
        adapter.send({"recipient": "+14155552671", "data": {"type": "text", "text": "hello"}})
    assert error.value.retryable is True
    assert error.value.retry_after == 23


@pytest.mark.parametrize(
    ("failure", "retryable", "error_code"),
    [
        (requests.ConnectTimeout("connect timed out"), True, "CONNECT_TIMEOUT"),
        (requests.ReadTimeout("read timed out"), False, "DELIVERY_OUTCOME_UNKNOWN"),
        (requests.ConnectionError("connection reset"), False, "DELIVERY_OUTCOME_UNKNOWN"),
    ],
)
def test_send_transport_errors_do_not_automatically_duplicate_unknown_delivery(failure, retryable, error_code):
    class FailingSession:
        def post(self, *args, **kwargs):
            raise failure

    adapter = WhatsAppCloudAdapter(
        access_token="mock-secret-access-token",
        phone_number_id="123456789012345",
        session=FailingSession(),
    )
    with pytest.raises(ProviderError) as error:
        adapter.send({"recipient": "+14155552671", "data": {"type": "text", "text": "hello"}})
    assert error.value.retryable is retryable
    assert error.value.error_code == error_code
    if error_code == "DELIVERY_OUTCOME_UNKNOWN":
        assert str(error.value).startswith("DELIVERY_OUTCOME_UNKNOWN:")
