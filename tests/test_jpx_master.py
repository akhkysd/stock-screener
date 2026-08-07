import pandas as pd
import pytest

from src.data_sources.jpx_master import (
    SecurityRecord,
    fetch_master_bytes,
    normalize,
    upsert_securities,
)
from src.db import apply_schema, get_connection

RAW_COLUMNS = [
    "日付",
    "コード",
    "銘柄名",
    "市場・商品区分",
    "33業種コード",
    "33業種区分",
    "17業種コード",
    "17業種区分",
    "規模コード",
    "規模区分",
]


def _raw_row(code, name, market, s33c="50", s33n="水産・農林業", s17c="1", s17n="食品"):
    return [20260731, code, name, market, s33c, s33n, s17c, s17n, "6", "TOPIX Small 1"]


def test_normalize_keeps_only_domestic_prime_standard_growth_stocks():
    df = pd.DataFrame(
        [
            _raw_row("1301", "極洋", "プライム（内国株式）"),
            _raw_row("1305", "ｉＦｒｅｅＥＴＦ", "ETF・ETN", "-", "-", "-", "-"),
            _raw_row("9999", "テスト外国株", "プライム（外国株式）"),
            _raw_row("1234", "テストグロース", "グロース（内国株式）"),
        ],
        columns=RAW_COLUMNS,
    )

    records = normalize(df)

    codes = {r.code for r in records}
    assert codes == {"1301", "1234"}


def test_normalize_maps_fields_correctly():
    df = pd.DataFrame(
        [_raw_row("1301", "極洋", "プライム（内国株式）", "50", "水産・農林業", "1", "食品")],
        columns=RAW_COLUMNS,
    )

    records = normalize(df)

    assert records == [
        SecurityRecord(
            code="1301",
            name="極洋",
            market_segment="プライム（内国株式）",
            sector_33_code="50",
            sector_33_name="水産・農林業",
            sector_17_code="1",
            sector_17_name="食品",
        )
    ]


def test_upsert_securities_inserts_and_updates(tmp_path):
    conn = get_connection(":memory:")
    apply_schema(conn)
    record = SecurityRecord(
        code="1301",
        name="極洋",
        market_segment="プライム（内国株式）",
        sector_33_code="50",
        sector_33_name="水産・農林業",
        sector_17_code="1",
        sector_17_name="食品",
    )

    upsert_securities(conn, [record], updated_at="2026-08-07")
    row = conn.execute("SELECT * FROM securities_master WHERE code = '1301'").fetchone()
    assert row["name"] == "極洋"

    updated = SecurityRecord(**{**record.__dict__, "name": "極洋（改名）"})
    upsert_securities(conn, [updated], updated_at="2026-08-08")
    row = conn.execute("SELECT * FROM securities_master WHERE code = '1301'").fetchone()
    assert row["name"] == "極洋（改名）"
    assert conn.execute("SELECT COUNT(*) FROM securities_master").fetchone()[0] == 1


def test_fetch_master_bytes_raises_on_http_error(monkeypatch):
    class DummyResponse:
        status_code = 500

        def raise_for_status(self):
            raise RuntimeError("boom")

    def dummy_get(url, headers=None, timeout=None):
        return DummyResponse()

    monkeypatch.setattr("src.data_sources.jpx_master.requests.get", dummy_get)

    with pytest.raises(RuntimeError):
        fetch_master_bytes()


def test_fetch_master_bytes_returns_content(monkeypatch):
    class DummyResponse:
        status_code = 200
        content = b"dummy-xls-bytes"

        def raise_for_status(self):
            pass

    def dummy_get(url, headers=None, timeout=None):
        return DummyResponse()

    monkeypatch.setattr("src.data_sources.jpx_master.requests.get", dummy_get)

    result = fetch_master_bytes()
    assert result == b"dummy-xls-bytes"
