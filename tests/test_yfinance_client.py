import pandas as pd

from src.data_sources.yfinance_client import YFinancePriceClient


def _make_raw(tickers_data: dict) -> pd.DataFrame:
    """Mimic yf.download(..., group_by='ticker') output shape."""
    dates = pd.to_datetime(["2026-08-05", "2026-08-06"])
    frames = {}
    for ticker, rows in tickers_data.items():
        frames[ticker] = pd.DataFrame(rows, index=dates)
    return pd.concat(frames, axis=1)


def test_fetch_daily_prices_success_single_batch():
    raw = _make_raw(
        {
            "7203.T": [
                {"Open": 100, "High": 110, "Low": 95, "Close": 105, "Volume": 1000},
                {"Open": 105, "High": 115, "Low": 100, "Close": 110, "Volume": 1200},
            ],
            "6758.T": [
                {"Open": 200, "High": 210, "Low": 195, "Close": 205, "Volume": 500},
                {"Open": 205, "High": 215, "Low": 200, "Close": 210, "Volume": 600},
            ],
        }
    )
    calls = []

    def fake_downloader(tickers, **kwargs):
        calls.append(tickers)
        return raw

    client = YFinancePriceClient(downloader=fake_downloader, sleep=lambda _: None)
    result = client.fetch_daily_prices(["7203", "6758"], "2026-08-05", "2026-08-07")

    assert result.failed_codes == []
    assert len(result.prices) == 4
    assert set(result.prices["code"]) == {"7203", "6758"}
    row = result.prices[(result.prices["code"] == "7203") & (result.prices["date"] == "2026-08-05")]
    assert row.iloc[0]["close"] == 105
    assert len(calls) == 1


def test_fetch_daily_prices_marks_missing_ticker_as_failed():
    raw = _make_raw(
        {
            "7203.T": [
                {"Open": 100, "High": 110, "Low": 95, "Close": 105, "Volume": 1000},
                {"Open": 105, "High": 115, "Low": 100, "Close": 110, "Volume": 1200},
            ],
            "9999.T": [
                {"Open": None, "High": None, "Low": None, "Close": None, "Volume": None},
                {"Open": None, "High": None, "Low": None, "Close": None, "Volume": None},
            ],
        }
    )

    client = YFinancePriceClient(downloader=lambda tickers, **kw: raw, sleep=lambda _: None)
    result = client.fetch_daily_prices(["7203", "9999"], "2026-08-05", "2026-08-07")

    assert result.failed_codes == ["9999"]
    assert set(result.prices["code"]) == {"7203"}


def test_fetch_daily_prices_batches_and_pauses_between_batches():
    raw = _make_raw(
        {
            "1.T": [{"Open": 1, "High": 1, "Low": 1, "Close": 1, "Volume": 1}] * 2,
        }
    )
    calls = []
    sleeps = []

    def fake_downloader(tickers, **kwargs):
        calls.append(list(tickers))
        return raw

    client = YFinancePriceClient(batch_size=1, downloader=fake_downloader, sleep=sleeps.append)
    client.fetch_daily_prices(["1", "2", "3"], "2026-08-05", "2026-08-07")

    assert len(calls) == 3
    # pause happens between batches only (n-1 pauses for n batches)
    assert len(sleeps) == 2


def test_fetch_daily_prices_batch_failure_does_not_abort_whole_run():
    def flaky_downloader(tickers, **kwargs):
        if tickers == ["2.T"]:
            raise RuntimeError("HTTP 429")
        ticker = tickers[0]
        return _make_raw({ticker: [{"Open": 1, "High": 1, "Low": 1, "Close": 1, "Volume": 1}] * 2})

    client = YFinancePriceClient(
        batch_size=1, downloader=flaky_downloader, sleep=lambda _: None, max_retries=1
    )
    result = client.fetch_daily_prices(["1", "2", "3"], "2026-08-05", "2026-08-07")

    assert "2" in result.failed_codes
    assert set(result.prices["code"]) == {"1", "3"}


def test_retry_exhausted_error_is_caught_internally(monkeypatch):
    def always_raises(tickers, **kwargs):
        raise RuntimeError("boom")

    client = YFinancePriceClient(
        batch_size=2, downloader=always_raises, sleep=lambda _: None, max_retries=1
    )
    result = client.fetch_daily_prices(["1", "2"], "2026-08-05", "2026-08-07")

    assert result.failed_codes == ["1", "2"]
    assert result.prices.empty
