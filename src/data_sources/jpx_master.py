import io
import sqlite3
from dataclasses import dataclass

import pandas as pd
import requests

JPX_MASTER_URL = (
    "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
)
REQUEST_TIMEOUT_SECONDS = 30
USER_AGENT = "Mozilla/5.0 (compatible; stock-screener/0.1; +https://github.com/)"

TARGET_MARKET_SEGMENTS = {
    "プライム（内国株式）",
    "スタンダード（内国株式）",
    "グロース（内国株式）",
}


@dataclass(frozen=True)
class SecurityRecord:
    code: str
    name: str
    market_segment: str
    sector_33_code: str | None
    sector_33_name: str | None
    sector_17_code: str | None
    sector_17_name: str | None


def fetch_master_bytes(url: str = JPX_MASTER_URL) -> bytes:
    response = requests.get(
        url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT_SECONDS
    )
    response.raise_for_status()
    return response.content


def normalize(df: pd.DataFrame) -> list[SecurityRecord]:
    filtered = df[df["市場・商品区分"].isin(TARGET_MARKET_SEGMENTS)]

    def _none_if_blank(value: object) -> str | None:
        text = str(value).strip()
        return None if text in ("", "-", "nan") else text

    records = [
        SecurityRecord(
            code=str(row["コード"]).strip(),
            name=str(row["銘柄名"]).strip(),
            market_segment=str(row["市場・商品区分"]).strip(),
            sector_33_code=_none_if_blank(row["33業種コード"]),
            sector_33_name=_none_if_blank(row["33業種区分"]),
            sector_17_code=_none_if_blank(row["17業種コード"]),
            sector_17_name=_none_if_blank(row["17業種区分"]),
        )
        for _, row in filtered.iterrows()
    ]
    return records


def upsert_securities(
    conn: sqlite3.Connection, records: list[SecurityRecord], updated_at: str
) -> None:
    conn.executemany(
        """
        INSERT INTO securities_master
            (code, name, market_segment, sector_33_code, sector_33_name,
             sector_17_code, sector_17_name, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
            name=excluded.name,
            market_segment=excluded.market_segment,
            sector_33_code=excluded.sector_33_code,
            sector_33_name=excluded.sector_33_name,
            sector_17_code=excluded.sector_17_code,
            sector_17_name=excluded.sector_17_name,
            updated_at=excluded.updated_at
        """,
        [
            (
                r.code,
                r.name,
                r.market_segment,
                r.sector_33_code,
                r.sector_33_name,
                r.sector_17_code,
                r.sector_17_name,
                updated_at,
            )
            for r in records
        ],
    )
    conn.commit()


def update_master(conn: sqlite3.Connection, updated_at: str, url: str = JPX_MASTER_URL) -> int:
    raw_bytes = fetch_master_bytes(url)
    df = pd.read_excel(io.BytesIO(raw_bytes), engine="xlrd")
    records = normalize(df)
    upsert_securities(conn, records, updated_at)
    return len(records)
