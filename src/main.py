import argparse
import datetime as dt
import sqlite3
from pathlib import Path
from typing import Protocol

import pandas as pd

from src.data_sources.base import PriceFetchResult
from src.data_sources.jpx_master import update_master
from src.data_sources.yfinance_client import YFinancePriceClient
from src.data_sources.yfinance_fundamentals import (
    FundamentalsFetchResult,
    YFinanceFundamentalsClient,
)
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
from src.report.report_generator import generate_markdown_report
from src.scoring.composite_score import compute_composite_scores, load_weights
from src.scoring.fundamental_score import compute_fundamental_zscores
from src.scoring.technical_score import compute_technical_indicators
from src.sector.sector_aggregation import compute_sector_ranking

DEFAULT_DB_PATH = "data/stock_screener.db"
DEFAULT_REPORTS_DIR = "data/reports"
PRICE_LOOKBACK_DAYS = 400
PRICE_INCREMENTAL_LOOKBACK_DAYS = 5
FUNDAMENTALS_MAX_AGE_DAYS = 7


class PriceClient(Protocol):
    def fetch_daily_prices(self, codes: list[str], start: str, end: str) -> PriceFetchResult: ...


class FundamentalsClient(Protocol):
    def fetch_fundamentals(self, codes: list[str]) -> FundamentalsFetchResult: ...


def run_daily_batch(
    conn: sqlite3.Connection,
    price_client: PriceClient,
    fundamentals_client: FundamentalsClient,
    weights: dict,
    run_date: str,
    codes: list[str] | None = None,
) -> tuple[str, pd.DataFrame]:
    all_codes = codes if codes is not None else get_all_codes(conn)
    classification = weights["sector"]["classification"]
    sector_map = get_sector_map(conn, classification=classification)

    run_date_obj = dt.date.fromisoformat(run_date)
    lookback_start = (run_date_obj - dt.timedelta(days=PRICE_LOOKBACK_DAYS)).isoformat()
    incremental_start = (
        run_date_obj - dt.timedelta(days=PRICE_INCREMENTAL_LOOKBACK_DAYS)
    ).isoformat()

    missing_today = codes_missing_for_date(conn, all_codes, run_date)
    has_history = codes_with_price_history(conn, missing_today)
    new_codes = [c for c in missing_today if c not in has_history]
    existing_codes = [c for c in missing_today if c in has_history]

    price_failed: list[str] = []
    for codes_to_fetch, start in ((new_codes, lookback_start), (existing_codes, incremental_start)):
        if not codes_to_fetch:
            continue
        price_result = price_client.fetch_daily_prices(codes_to_fetch, start, run_date)
        if not price_result.prices.empty:
            upsert_daily_prices(conn, price_result.prices, source="yfinance")
        price_failed.extend(price_result.failed_codes)

    price_history = read_price_history(conn, all_codes, start_date=lookback_start)
    technical_indicators = compute_technical_indicators(price_history)
    latest_technical = (
        technical_indicators.sort_values("date").groupby("code").tail(1)
        if not technical_indicators.empty
        else technical_indicators
    )

    stale_codes = codes_stale_for_fundamentals(
        conn, all_codes, run_date, max_age_days=FUNDAMENTALS_MAX_AGE_DAYS
    )
    fundamentals_failed: list[str] = []
    if stale_codes:
        fundamentals_result = fundamentals_client.fetch_fundamentals(stale_codes)
        if not fundamentals_result.fundamentals.empty:
            upsert_yfinance_fundamentals(
                conn, fundamentals_result.fundamentals, updated_at=run_date
            )
        fundamentals_failed = fundamentals_result.failed_codes

    fundamentals_df = read_yfinance_fundamentals(conn, all_codes)
    fundamentals_df["sector"] = fundamentals_df["code"].map(sector_map)
    fundamentals_df = fundamentals_df.dropna(subset=["sector"])

    fundamental_scores = compute_fundamental_zscores(fundamentals_df)
    composite = compute_composite_scores(fundamental_scores, latest_technical, weights)
    ranking = compute_sector_ranking(composite)

    names = {
        row["code"]: row["name"] for row in conn.execute("SELECT code, name FROM securities_master")
    }
    ranking = ranking.copy()
    ranking["name"] = ranking["code"].map(names)

    unscored_mask = ranking["composite_score"].isna()
    missing_codes = sorted(
        set(price_failed)
        | set(fundamentals_failed)
        | (set(all_codes) - set(ranking["code"]))
        | set(ranking.loc[unscored_mask, "code"])
    )

    report = generate_markdown_report(run_date, ranking[~unscored_mask], missing_codes)
    insert_report_output(conn, run_date, ranking)
    return report, ranking


def main() -> None:
    parser = argparse.ArgumentParser(description="国内割安・底値株デイリーレポート バッチ")
    parser.add_argument("--limit", type=int, default=None, help="動作確認用に対象銘柄数を制限")
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH)
    parser.add_argument("--skip-master-update", action="store_true")
    args = parser.parse_args()

    Path(args.db_path).parent.mkdir(parents=True, exist_ok=True)
    Path(DEFAULT_REPORTS_DIR).mkdir(parents=True, exist_ok=True)

    conn = get_connection(args.db_path)
    apply_schema(conn)

    if not args.skip_master_update:
        count = update_master(conn, updated_at=dt.date.today().isoformat())
        print(f"銘柄マスタ更新: {count}件")

    run_date = dt.date.today().isoformat()
    codes = get_all_codes(conn)
    if args.limit:
        codes = codes[: args.limit]

    weights = load_weights()
    price_client = YFinancePriceClient()
    fundamentals_client = YFinanceFundamentalsClient()

    report, ranking = run_daily_batch(
        conn, price_client, fundamentals_client, weights, run_date, codes=codes
    )

    report_path = Path(DEFAULT_REPORTS_DIR) / f"{run_date}.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"レポート出力: {report_path}")
    print(f"対象銘柄数: {len(ranking)}")


if __name__ == "__main__":
    main()
