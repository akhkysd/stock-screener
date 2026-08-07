from dataclasses import dataclass, field

import pytest

from src.data_sources.edinet_client import EdinetClient


@dataclass
class FakeResponse:
    status_code: int = 200
    _json: dict = field(default_factory=dict)
    content: bytes = b""

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._json


def test_list_documents_passes_subscription_key_and_date():
    calls = []

    def fake_get(url, params, timeout):
        calls.append((url, params))
        return FakeResponse(_json={"results": [{"docID": "S100ABCD", "formCode": "030000"}]})

    client = EdinetClient(api_key="TESTKEY", get_func=fake_get, sleep=lambda _: None)
    results = client.list_documents("2026-08-07")

    assert results == [{"docID": "S100ABCD", "formCode": "030000"}]
    url, params = calls[0]
    assert "documents.json" in url
    assert params["date"] == "2026-08-07"
    assert params["Subscription-Key"] == "TESTKEY"
    assert params["type"] == "2"


def test_list_documents_returns_empty_list_when_no_results_key():
    client = EdinetClient(
        api_key="TESTKEY",
        get_func=lambda url, params, timeout: FakeResponse(_json={}),
        sleep=lambda _: None,
    )
    assert client.list_documents("2026-08-07") == []


def test_fetch_document_csv_requests_type_5_and_returns_bytes():
    calls = []

    def fake_get(url, params, timeout):
        calls.append((url, params))
        return FakeResponse(content=b"PK\x03\x04dummy-zip-bytes")

    client = EdinetClient(api_key="TESTKEY", get_func=fake_get, sleep=lambda _: None)
    result = client.fetch_document_csv("S100ABCD")

    assert result == b"PK\x03\x04dummy-zip-bytes"
    url, params = calls[0]
    assert "S100ABCD" in url
    assert params["type"] == "5"
    assert params["Subscription-Key"] == "TESTKEY"


def test_throttle_sleeps_between_consecutive_requests():
    sleeps = []
    times = iter([100.0, 101.0])

    client = EdinetClient(
        api_key="TESTKEY",
        get_func=lambda url, params, timeout: FakeResponse(_json={"results": []}),
        sleep=sleeps.append,
        min_interval=3.0,
        max_interval=3.0,
        monotonic=lambda: next(times),
    )
    client.list_documents("2026-08-07")
    client.list_documents("2026-08-07")

    assert len(sleeps) == 1
    assert sleeps[0] == pytest.approx(2.0, abs=0.01)


def test_raises_after_retries_exhausted_on_persistent_error():
    def always_fails(url, params, timeout):
        return FakeResponse(status_code=500)

    client = EdinetClient(
        api_key="TESTKEY", get_func=always_fails, sleep=lambda _: None, max_retries=1
    )

    with pytest.raises(Exception):
        client.list_documents("2026-08-07")
