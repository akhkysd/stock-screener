import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field

import pandas as pd

from src.data_sources.edinet_csv_parser import parse_financial_csv

# 有価証券報告書=030000は仕様書で確認済み。四半期報告書=043000・臨時報告書=050000は
# 未検証（EDINET APIキー取得後に実データで確認する）。
TARGET_FORM_CODES = {"030000", "043000", "050000"}

FUNDAMENTALS_FIELDS = ["eps", "bps", "net_income", "equity", "shares_outstanding"]


@dataclass
class FundamentalsUpdateResult:
    updated_codes: list[str] = field(default_factory=list)
    failed_doc_ids: list[str] = field(default_factory=list)


def is_target_document(doc: dict, target_codes: set[str]) -> bool:
    sec_code = doc.get("secCode") or ""
    form_code = doc.get("formCode") or ""
    return sec_code[:4] in target_codes and form_code in TARGET_FORM_CODES


def filter_target_documents(docs: list[dict], target_codes: set[str]) -> list[dict]:
    return [doc for doc in docs if is_target_document(doc, target_codes)]


def upsert_fundamentals(
    conn: sqlite3.Connection,
    code: str,
    fiscal_period: str,
    financials: dict,
    doc_id: str,
    updated_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO fundamentals
            (code, fiscal_period, eps, bps, net_income, equity, shares_outstanding,
             doc_id, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(code, fiscal_period) DO UPDATE SET
            eps=excluded.eps,
            bps=excluded.bps,
            net_income=excluded.net_income,
            equity=excluded.equity,
            shares_outstanding=excluded.shares_outstanding,
            doc_id=excluded.doc_id,
            updated_at=excluded.updated_at
        """,
        (
            code,
            fiscal_period,
            financials.get("eps"),
            financials.get("bps"),
            financials.get("net_income"),
            financials.get("equity"),
            financials.get("shares_outstanding"),
            doc_id,
            updated_at,
        ),
    )
    conn.commit()


def update_fundamentals_from_documents(
    conn: sqlite3.Connection,
    client,
    date: str,
    target_codes: set[str],
    updated_at: str,
    csv_parser: Callable[[bytes], dict] = parse_financial_csv,
) -> FundamentalsUpdateResult:
    docs = client.list_documents(date)
    targets = filter_target_documents(docs, target_codes)

    result = FundamentalsUpdateResult()
    for doc in targets:
        doc_id = doc["docID"]
        code = (doc.get("secCode") or "")[:4]
        try:
            zip_bytes = client.fetch_document_csv(doc_id)
            financials = csv_parser(zip_bytes)
        except Exception:
            result.failed_doc_ids.append(doc_id)
            continue
        fiscal_period = doc.get("periodEnd") or date
        upsert_fundamentals(conn, code, fiscal_period, financials, doc_id, updated_at)
        result.updated_codes.append(code)
    return result


def compute_verified_fundamentals(
    edinet_fundamentals_df: pd.DataFrame,
    latest_prices: pd.DataFrame,
    yfinance_fallback_df: pd.DataFrame,
) -> pd.DataFrame:
    """EDINET一次データを優先し、無い銘柄のみyfinance参考値で補完する。"""
    merged = edinet_fundamentals_df.merge(latest_prices, on="code", how="inner")
    verified = pd.DataFrame(
        {
            "code": merged.get("code", pd.Series(dtype=str)),
            "per": merged["close"] / merged["eps"] if "eps" in merged else pd.Series(dtype=float),
            "pbr": merged["close"] / merged["bps"] if "bps" in merged else pd.Series(dtype=float),
            "roe": (
                merged["net_income"] / merged["equity"]
                if "net_income" in merged
                else pd.Series(dtype=float)
            ),
        }
    )
    verified["source"] = "edinet"

    fallback_codes = set(yfinance_fallback_df["code"]) - set(verified["code"])
    fallback = yfinance_fallback_df[yfinance_fallback_df["code"].isin(fallback_codes)].copy()
    fallback["source"] = "yfinance"

    return pd.concat(
        [verified, fallback[["code", "per", "pbr", "roe", "source"]]], ignore_index=True
    )
