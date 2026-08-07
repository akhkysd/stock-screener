import sqlite3
from pathlib import Path

import pandas as pd

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "config" / "schema.sql"


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def apply_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


def get_all_codes(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT code FROM securities_master").fetchall()
    return [row["code"] for row in rows]


def get_sector_map(conn: sqlite3.Connection, classification: str = "33") -> dict[str, str]:
    column = "sector_33_name" if classification == "33" else "sector_17_name"
    rows = conn.execute(f"SELECT code, {column} AS sector FROM securities_master").fetchall()
    return {row["code"]: row["sector"] for row in rows}


def upsert_daily_prices(conn: sqlite3.Connection, prices_df: pd.DataFrame, source: str) -> None:
    conn.executemany(
        """
        INSERT INTO daily_price (code, date, open, high, low, close, volume, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(code, date) DO UPDATE SET
            open=excluded.open,
            high=excluded.high,
            low=excluded.low,
            close=excluded.close,
            volume=excluded.volume,
            source=excluded.source
        """,
        [
            (r.code, r.date, r.open, r.high, r.low, r.close, r.volume, source)
            for r in prices_df.itertuples()
        ],
    )
    conn.commit()


def read_price_history(conn: sqlite3.Connection, codes: list[str], start_date: str) -> pd.DataFrame:
    if not codes:
        return pd.DataFrame(columns=["code", "date", "open", "high", "low", "close", "volume"])
    placeholders = ",".join("?" * len(codes))
    query = (
        "SELECT code, date, open, high, low, close, volume FROM daily_price "
        f"WHERE code IN ({placeholders}) AND date >= ? ORDER BY code, date"
    )
    return pd.read_sql_query(query, conn, params=[*codes, start_date])


def codes_missing_for_date(conn: sqlite3.Connection, codes: list[str], date: str) -> list[str]:
    if not codes:
        return []
    placeholders = ",".join("?" * len(codes))
    rows = conn.execute(
        f"SELECT code FROM daily_price WHERE date = ? AND code IN ({placeholders})",
        [date, *codes],
    ).fetchall()
    existing = {row["code"] for row in rows}
    return [c for c in codes if c not in existing]


def insert_report_output(conn: sqlite3.Connection, date: str, ranking_df: pd.DataFrame) -> None:
    conn.execute("DELETE FROM report_output WHERE date = ?", (date,))
    conn.executemany(
        "INSERT INTO report_output (date, sector, rank, code, comment) VALUES (?, ?, ?, ?, ?)",
        [
            (
                date,
                r.sector,
                None if pd.isna(r.sector_rank) else int(r.sector_rank),
                r.code,
                None,
            )
            for r in ranking_df.itertuples()
        ],
    )
    conn.commit()
