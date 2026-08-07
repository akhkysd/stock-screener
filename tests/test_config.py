from src.config import load_edinet_api_key


def test_load_edinet_api_key_reads_from_environ(monkeypatch):
    monkeypatch.setenv("EDINET_API_KEY", "abc123")
    assert load_edinet_api_key() == "abc123"


def test_load_edinet_api_key_returns_none_when_unset(monkeypatch):
    monkeypatch.delenv("EDINET_API_KEY", raising=False)
    assert load_edinet_api_key() is None
