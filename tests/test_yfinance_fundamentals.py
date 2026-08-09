import pandas as pd

from src.data_sources.yfinance_fundamentals import YFinanceFundamentalsClient


def test_fetch_fundamentals_extracts_expected_fields():
    def info_provider(ticker):
        assert ticker == "7203.T"
        return {"trailingPE": 8.5, "priceToBook": 0.97, "returnOnEquity": 0.124}

    client = YFinanceFundamentalsClient(info_provider=info_provider, sleep=lambda _: None)
    result = client.fetch_fundamentals(["7203"])

    assert result.failed_codes == []
    row = result.fundamentals[result.fundamentals["code"] == "7203"].iloc[0]
    assert row["per"] == 8.5
    assert row["pbr"] == 0.97
    assert row["roe"] == 0.124


def test_fetch_fundamentals_handles_missing_fields():
    client = YFinanceFundamentalsClient(info_provider=lambda t: {}, sleep=lambda _: None)
    result = client.fetch_fundamentals(["7203"])

    row = result.fundamentals[result.fundamentals["code"] == "7203"].iloc[0]
    assert pd.isna(row["per"])
    assert pd.isna(row["pbr"])
    assert pd.isna(row["roe"])


def test_fetch_fundamentals_marks_failures_without_aborting(monkeypatch):
    def flaky_provider(ticker):
        if ticker == "9999.T":
            raise RuntimeError("boom")
        return {"trailingPE": 10.0, "priceToBook": 1.0, "returnOnEquity": 0.1}

    client = YFinanceFundamentalsClient(
        info_provider=flaky_provider, sleep=lambda _: None, max_retries=1
    )
    result = client.fetch_fundamentals(["7203", "9999"])

    assert result.failed_codes == ["9999"]
    assert set(result.fundamentals["code"]) == {"7203"}


def test_fetch_fundamentals_coerces_non_numeric_info_values_to_none():
    def info_provider(ticker):
        # yfinance occasionally returns non-numeric strings/placeholders for these
        # fields on some tickers (observed in a full-universe run)
        return {"trailingPE": "Infinity", "priceToBook": "N/A", "returnOnEquity": 0.1}

    client = YFinanceFundamentalsClient(info_provider=info_provider, sleep=lambda _: None)
    result = client.fetch_fundamentals(["7203"])

    row = result.fundamentals.iloc[0]
    assert pd.isna(row["per"])
    assert pd.isna(row["pbr"])
    assert row["roe"] == 0.1
    assert pd.api.types.is_numeric_dtype(result.fundamentals["per"])


def test_fetch_fundamentals_column_dtype_is_numeric_even_with_mixed_bad_values():
    def info_provider(ticker):
        if ticker == "1111.T":
            return {"trailingPE": "bad", "priceToBook": 1.0, "returnOnEquity": 0.1}
        return {"trailingPE": 10.0, "priceToBook": 1.0, "returnOnEquity": 0.1}

    client = YFinanceFundamentalsClient(info_provider=info_provider, sleep=lambda _: None)
    result = client.fetch_fundamentals(["1111", "7203"])

    assert pd.api.types.is_numeric_dtype(result.fundamentals["per"])


def test_fetch_fundamentals_sleeps_between_requests():
    sleeps = []
    client = YFinanceFundamentalsClient(
        info_provider=lambda t: {"trailingPE": 1.0, "priceToBook": 1.0, "returnOnEquity": 1.0},
        sleep=sleeps.append,
    )
    client.fetch_fundamentals(["1", "2", "3"])

    assert len(sleeps) == 2
