import sqlite3

from src.db import apply_schema, get_connection

EXPECTED_TABLES = {
    "securities_master",
    "daily_price",
    "technical_score",
    "valuation_score",
    "fundamentals",
    "yfinance_fundamentals_cache",
    "report_output",
}


def test_apply_schema_creates_expected_tables():
    conn = get_connection(":memory:")
    apply_schema(conn)

    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = {row[0] for row in rows}

    assert EXPECTED_TABLES <= table_names


def test_get_connection_returns_row_factory_dict_like():
    conn = get_connection(":memory:")
    apply_schema(conn)
    conn.execute(
        "INSERT INTO securities_master (code, name, updated_at) VALUES (?, ?, ?)",
        ("7203", "トヨタ自動車", "2026-08-07"),
    )
    conn.commit()

    row = conn.execute("SELECT * FROM securities_master WHERE code = '7203'").fetchone()

    assert row["name"] == "トヨタ自動車"
    assert isinstance(conn.row_factory, type) or conn.row_factory is sqlite3.Row
