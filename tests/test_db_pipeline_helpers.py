import pandas as pd
import pytest

from src.data_sources.jpx_master import SecurityRecord, upsert_securities
from src.db import (
    apply_schema,
    codes_missing_for_date,
    codes_stale_for_fundamentals,
    codes_with_price_history,
    get_all_codes,
    get_connection,
    get_sector_map,
    insert_report_output,
    read_price_history,
    read_yfinance_fundamentals,
    upsert_daily_prices,
    upsert_yfinance_fundamentals,
)


@pytest.fixture
def conn():
    c = get_connection(":memory:")
    apply_schema(c)
    return c


def _seed_securities(conn):
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
    upsert_securities(conn, records, updated_at="2026-08-07")


def test_get_all_codes_returns_all_master_codes(conn):
    _seed_securities(conn)
    assert set(get_all_codes(conn)) == {"1301", "7203"}


def test_get_sector_map_returns_33_sector_by_default(conn):
    _seed_securities(conn)
    mapping = get_sector_map(conn)
    assert mapping["1301"] == "水産・農林業"
    assert mapping["7203"] == "輸送用機器"


def test_get_sector_map_can_use_17_sector(conn):
    _seed_securities(conn)
    mapping = get_sector_map(conn, classification="17")
    assert mapping["1301"] == "食品"
    assert mapping["7203"] == "自動車・輸送機"


def test_upsert_and_read_price_history_round_trip(conn):
    prices = pd.DataFrame(
        [
            {
                "code": "1301",
                "date": "2026-08-05",
                "open": 100.0,
                "high": 110.0,
                "low": 95.0,
                "close": 105.0,
                "volume": 1000,
            },
            {
                "code": "1301",
                "date": "2026-08-06",
                "open": 105.0,
                "high": 115.0,
                "low": 100.0,
                "close": 110.0,
                "volume": 1200,
            },
        ]
    )
    upsert_daily_prices(conn, prices, source="yfinance")

    history = read_price_history(conn, ["1301"], start_date="2026-08-01")

    assert len(history) == 2
    assert set(history["date"]) == {"2026-08-05", "2026-08-06"}


def test_upsert_daily_prices_overwrites_same_day(conn):
    prices = pd.DataFrame(
        [
            {
                "code": "1301",
                "date": "2026-08-05",
                "open": 1,
                "high": 1,
                "low": 1,
                "close": 1,
                "volume": 1,
            }
        ]
    )
    upsert_daily_prices(conn, prices, source="yfinance")
    updated = pd.DataFrame(
        [
            {
                "code": "1301",
                "date": "2026-08-05",
                "open": 2,
                "high": 2,
                "low": 2,
                "close": 2,
                "volume": 2,
            }
        ]
    )
    upsert_daily_prices(conn, updated, source="stooq")

    history = read_price_history(conn, ["1301"], start_date="2026-08-01")
    assert len(history) == 1
    assert history.iloc[0]["close"] == 2


def test_codes_missing_for_date(conn):
    prices = pd.DataFrame(
        [
            {
                "code": "1301",
                "date": "2026-08-07",
                "open": 1,
                "high": 1,
                "low": 1,
                "close": 1,
                "volume": 1,
            }
        ]
    )
    upsert_daily_prices(conn, prices, source="yfinance")

    missing = codes_missing_for_date(conn, ["1301", "7203"], date="2026-08-07")

    assert missing == ["7203"]


def test_codes_with_price_history(conn):
    prices = pd.DataFrame(
        [
            {
                "code": "1301",
                "date": "2026-07-01",
                "open": 1,
                "high": 1,
                "low": 1,
                "close": 1,
                "volume": 1,
            }
        ]
    )
    upsert_daily_prices(conn, prices, source="yfinance")

    result = codes_with_price_history(conn, ["1301", "7203"])

    assert result == {"1301"}


def test_codes_with_price_history_empty_input_returns_empty_set(conn):
    assert codes_with_price_history(conn, []) == set()


def test_codes_stale_for_fundamentals_treats_never_cached_as_stale(conn):
    result = codes_stale_for_fundamentals(conn, ["1301", "7203"], as_of_date="2026-08-07")
    assert set(result) == {"1301", "7203"}


def test_codes_stale_for_fundamentals_excludes_recently_cached(conn):
    df = pd.DataFrame([{"code": "1301", "per": 10.0, "pbr": 1.0, "roe": 0.1}])
    upsert_yfinance_fundamentals(conn, df, updated_at="2026-08-05")

    result = codes_stale_for_fundamentals(
        conn, ["1301", "7203"], as_of_date="2026-08-07", max_age_days=7
    )

    assert result == ["7203"]


def test_codes_stale_for_fundamentals_includes_old_cache_entries(conn):
    df = pd.DataFrame([{"code": "1301", "per": 10.0, "pbr": 1.0, "roe": 0.1}])
    upsert_yfinance_fundamentals(conn, df, updated_at="2026-07-01")

    result = codes_stale_for_fundamentals(conn, ["1301"], as_of_date="2026-08-07", max_age_days=7)

    assert result == ["1301"]


def test_upsert_and_read_yfinance_fundamentals_round_trip(conn):
    df = pd.DataFrame(
        [
            {"code": "1301", "per": 10.0, "pbr": 1.0, "roe": 0.1},
            {"code": "7203", "per": 8.5, "pbr": 1.0, "roe": 0.12},
        ]
    )
    upsert_yfinance_fundamentals(conn, df, updated_at="2026-08-07")

    result = read_yfinance_fundamentals(conn, ["1301", "7203"])
    result = result.set_index("code")

    assert result.loc["1301", "per"] == 10.0
    assert result.loc["7203", "roe"] == 0.12


def test_upsert_yfinance_fundamentals_overwrites_existing(conn):
    upsert_yfinance_fundamentals(
        conn, pd.DataFrame([{"code": "1301", "per": 10.0, "pbr": 1.0, "roe": 0.1}]), "2026-08-01"
    )
    upsert_yfinance_fundamentals(
        conn, pd.DataFrame([{"code": "1301", "per": 20.0, "pbr": 2.0, "roe": 0.2}]), "2026-08-07"
    )

    result = read_yfinance_fundamentals(conn, ["1301"])

    assert len(result) == 1
    assert result.iloc[0]["per"] == 20.0


def test_insert_report_output_handles_nan_rank(conn):
    ranking_df = pd.DataFrame([{"code": "1301", "sector": "食品", "sector_rank": pd.NA}]).astype(
        {"sector_rank": "Int64"}
    )

    insert_report_output(conn, date="2026-08-07", ranking_df=ranking_df)

    row = conn.execute("SELECT rank FROM report_output").fetchone()
    assert row["rank"] is None


def test_insert_report_output(conn):
    ranking_df = pd.DataFrame(
        [
            {"code": "1301", "sector": "食品", "sector_rank": 1},
            {"code": "7203", "sector": "自動車・輸送機", "sector_rank": 1},
        ]
    )
    insert_report_output(conn, date="2026-08-07", ranking_df=ranking_df)

    rows = conn.execute("SELECT * FROM report_output").fetchall()
    assert len(rows) == 2
