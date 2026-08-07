import argparse
from pathlib import Path

from src.backtest.backtest import (
    backtest_signal,
    generate_backtest_markdown,
    low52w_near_signal,
    ma25_dip_signal,
    rsi_oversold_signal,
)
from src.db import get_all_codes, get_connection, read_price_history
from src.scoring.composite_score import load_weights

DEFAULT_OUTPUT_PATH = "data/backtest_report.md"


def main() -> None:
    parser = argparse.ArgumentParser(description="テクニカルシグナルのバックテスト")
    parser.add_argument("--db-path", default="data/stock_screener.db")
    parser.add_argument("--start-date", default="2000-01-01")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    conn = get_connection(args.db_path)
    codes = get_all_codes(conn)
    price_df = read_price_history(conn, codes, start_date=args.start_date)

    weights = load_weights()
    thresholds = weights["thresholds"]

    signals = {
        "RSI14が閾値以下": rsi_oversold_signal(thresholds["rsi_oversold"]),
        "25日線からの下方乖離": ma25_dip_signal(thresholds["ma25_deviation_threshold"]),
        "52週安値圏": low52w_near_signal(thresholds["low52w_deviation_threshold"]),
    }

    results = {name: backtest_signal(price_df, fn) for name, fn in signals.items()}
    report = generate_backtest_markdown(results)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"バックテスト結果: {output_path}")


if __name__ == "__main__":
    main()
