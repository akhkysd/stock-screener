from dataclasses import dataclass, field

import pandas as pd
import pytest

from src.data_sources.jpx_master import SecurityRecord, upsert_securities
from src.db import apply_schema, get_connection
from src.main import run_daily_batch
from src.scoring.composite_score import load_weights


@dataclass
class FakePriceResult:
    prices: pd.DataFrame
    failed_codes: list = field(default_factory=list)


@dataclass
class FakeFundamentalsResult:
    fundamentals: pd.DataFrame
    failed_codes: list = field(default_factory=list)


class FakePriceClient:
    def __init__(self, prices: pd.DataFrame, failed: list | None = None):
        self._prices = prices
        self._failed = failed or []
        self.calls = []

    def fetch_daily_prices(self, codes, start, end):
        self.calls.append({"codes": list(codes), "start": start, "end": end})
        subset = self._prices[
            self._prices["code"].isin(codes)
            & (self._prices["date"] >= start)
            & (self._prices["date"] <= end)
        ]
        return FakePriceResult(prices=subset.copy(), failed_codes=self._failed)


class FakeFundamentalsClient:
    def __init__(self, fundamentals: pd.DataFrame, failed: list | None = None):
        self._fundamentals = fundamentals
        self._failed = failed or []

    def fetch_fundamentals(self, codes):
        return FakeFundamentalsResult(
            fundamentals=self._fundamentals[self._fundamentals["code"].isin(codes)].copy(),
            failed_codes=self._failed,
        )


@pytest.fixture
def conn():
    c = get_connection(":memory:")
    apply_schema(c)
    records = [
        SecurityRecord("1301", "極洋", "プライム（内国株式）", "50", "水産・農林業", "1", "食品"),
        SecurityRecord(
            "7203",
            "トヨタ自動車",
            "プライム（内国株式）",
            "3050",
            "輸送用機器",
            "9",
            "自動車・輸送機",
        ),
    ]
    upsert_securities(c, records, updated_at="2026-08-07")
    return c


def _price_df():
    dates = pd.date_range("2026-07-01", "2026-08-07", freq="B").strftime("%Y-%m-%d")
    rows = []
    for code, base in (("1301", 100.0), ("7203", 3000.0)):
        for i, date in enumerate(dates):
            rows.append(
                {
                    "code": code,
                    "date": date,
                    "open": base + i,
                    "high": base + i + 5,
                    "low": base + i - 5,
                    "close": base + i,
                    "volume": 1000,
                }
            )
    return pd.DataFrame(rows)


def _fundamentals_df():
    return pd.DataFrame(
        [
            {"code": "1301", "per": 10.0, "pbr": 1.0, "roe": 8.0},
            {"code": "7203", "per": 8.5, "pbr": 1.0, "roe": 12.0},
        ]
    )


def test_run_daily_batch_produces_report_and_ranking(conn):
    price_client = FakePriceClient(_price_df())
    fundamentals_client = FakeFundamentalsClient(_fundamentals_df())
    weights = load_weights()

    report, ranking = run_daily_batch(
        conn,
        price_client,
        fundamentals_client,
        weights,
        run_date="2026-08-07",
        codes=["1301", "7203"],
    )

    assert "2026-08-07" in report
    assert "極洋" in report
    assert "トヨタ自動車" in report
    assert len(ranking) == 2

    stored = conn.execute(
        "SELECT COUNT(*) FROM report_output WHERE date = '2026-08-07'"
    ).fetchone()[0]
    assert stored == 2

    stored_prices = conn.execute("SELECT COUNT(*) FROM daily_price").fetchone()[0]
    assert stored_prices > 0


def test_run_daily_batch_flags_failed_codes_as_missing(conn):
    price_client = FakePriceClient(_price_df(), failed=["9999"])
    fundamentals_client = FakeFundamentalsClient(_fundamentals_df())
    weights = load_weights()

    report, _ranking = run_daily_batch(
        conn,
        price_client,
        fundamentals_client,
        weights,
        run_date="2026-08-07",
        codes=["1301", "7203", "9999"],
    )

    assert "データ欠損銘柄" in report
    assert "9999" in report


def test_run_daily_batch_treats_unscored_code_as_missing_not_nan_row(conn):
    price_client = FakePriceClient(_price_df())
    fundamentals = pd.DataFrame(
        [
            {"code": "1301", "per": 10.0, "pbr": 1.0, "roe": 8.0},
            {"code": "7203", "per": None, "pbr": None, "roe": None},
        ]
    )
    fundamentals_client = FakeFundamentalsClient(fundamentals)
    weights = load_weights()

    report, ranking = run_daily_batch(
        conn,
        price_client,
        fundamentals_client,
        weights,
        run_date="2026-08-07",
        codes=["1301", "7203"],
    )

    assert "nan" not in report
    assert "データ欠損銘柄" in report
    assert "7203" in report.split("データ欠損銘柄")[1]
    # still recorded in the returned ranking / DB for reproducibility
    assert "7203" in set(ranking["code"])


def test_run_daily_batch_skips_refetch_for_already_cached_date(conn):
    price_client = FakePriceClient(_price_df())
    fundamentals_client = FakeFundamentalsClient(_fundamentals_df())
    weights = load_weights()

    run_daily_batch(
        conn,
        price_client,
        fundamentals_client,
        weights,
        run_date="2026-08-07",
        codes=["1301", "7203"],
    )
    calls_before = conn.execute("SELECT COUNT(*) FROM daily_price").fetchone()[0]

    # second run: price_client would raise if asked to fetch again for the same date
    class ExplodingPriceClient:
        def fetch_daily_prices(self, codes, start, end):
            raise AssertionError("should not refetch already-cached date")

    run_daily_batch(
        conn,
        ExplodingPriceClient(),
        fundamentals_client,
        weights,
        run_date="2026-08-07",
        codes=["1301", "7203"],
    )
    calls_after = conn.execute("SELECT COUNT(*) FROM daily_price").fetchone()[0]

    assert calls_after == calls_before


def test_run_daily_batch_uses_short_window_for_codes_with_existing_history(conn):
    fundamentals_client = FakeFundamentalsClient(_fundamentals_df())
    weights = load_weights()

    # day 1: both codes are brand new -> full lookback window
    day1_client = FakePriceClient(_price_df())
    run_daily_batch(
        conn,
        day1_client,
        fundamentals_client,
        weights,
        run_date="2026-08-06",
        codes=["1301", "7203"],
    )
    assert len(day1_client.calls) == 1
    day1_start = day1_client.calls[0]["start"]
    assert (
        pd.Timestamp("2026-08-06") - pd.Timestamp(day1_start)
    ).days > 300  # ~400-day backfill window

    # day 2: both codes already have history -> short incremental window only
    day2_client = FakePriceClient(_price_df())
    run_daily_batch(
        conn,
        day2_client,
        fundamentals_client,
        weights,
        run_date="2026-08-07",
        codes=["1301", "7203"],
    )
    assert len(day2_client.calls) == 1
    day2_start = day2_client.calls[0]["start"]
    assert (pd.Timestamp("2026-08-07") - pd.Timestamp(day2_start)).days <= 7
