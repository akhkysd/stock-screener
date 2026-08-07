from collections.abc import Callable

import pandas as pd

from src.scoring.technical_score import compute_technical_indicators

DEFAULT_HOLDING_DAYS = (5, 10, 20)

SignalFn = Callable[[pd.DataFrame], pd.Series]


def compute_forward_returns(
    price_df: pd.DataFrame, holding_days: tuple[int, ...] = DEFAULT_HOLDING_DAYS
) -> pd.DataFrame:
    columns = ["code", "date", *[f"return_{h}d" for h in holding_days]]
    if price_df.empty:
        return pd.DataFrame(columns=columns)

    frames = []
    for code, group in price_df.groupby("code", sort=False):
        group = group.sort_values("date").reset_index(drop=True)
        row = {"code": group["code"], "date": group["date"]}
        for h in holding_days:
            row[f"return_{h}d"] = group["close"].shift(-h) / group["close"] - 1
        frames.append(pd.DataFrame(row))
    return pd.concat(frames, ignore_index=True)


def backtest_signal(
    price_df: pd.DataFrame,
    signal_fn: SignalFn,
    holding_days: tuple[int, ...] = DEFAULT_HOLDING_DAYS,
) -> pd.DataFrame:
    """シグナル発生日を起点としたN日後リターンの的中率・平均リターンを集計する。"""
    indicators = compute_technical_indicators(price_df)
    returns = compute_forward_returns(price_df, holding_days)
    merged = indicators.merge(returns, on=["code", "date"])

    signal_rows = merged[signal_fn(merged)]

    results = []
    for h in holding_days:
        col = f"return_{h}d"
        signal_returns = signal_rows[col].dropna()
        baseline_returns = merged[col].dropna()
        results.append(
            {
                "holding_days": h,
                "signal_count": len(signal_returns),
                "signal_hit_rate": ((signal_returns > 0).mean() if len(signal_returns) else None),
                "signal_avg_return": signal_returns.mean() if len(signal_returns) else None,
                "baseline_avg_return": (baseline_returns.mean() if len(baseline_returns) else None),
            }
        )
    return pd.DataFrame(results)


def rsi_oversold_signal(threshold: float) -> SignalFn:
    def _signal(df: pd.DataFrame) -> pd.Series:
        return df["rsi14"] <= threshold

    return _signal


def ma25_dip_signal(threshold: float) -> SignalFn:
    def _signal(df: pd.DataFrame) -> pd.Series:
        return df["ma25_deviation"] <= threshold

    return _signal


def low52w_near_signal(threshold: float) -> SignalFn:
    def _signal(df: pd.DataFrame) -> pd.Series:
        return df["low52w_deviation"] <= threshold

    return _signal


def _fmt_pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value * 100:.1f}%"


def _fmt_return(value: float | None) -> str:
    return "N/A" if value is None else f"{value * 100:+.2f}%"


def generate_backtest_markdown(results_by_signal: dict[str, pd.DataFrame]) -> str:
    lines = ["# バックテスト結果（シグナル的中率・平均リターン）", ""]
    for name, df in results_by_signal.items():
        lines.append(f"## {name}")
        lines.append("")
        lines.append("| 保有日数 | 発生回数 | 的中率 | 平均リターン | ベースライン平均 |")
        lines.append("|---|---|---|---|---|")
        for _, row in df.iterrows():
            lines.append(
                f"| {int(row['holding_days'])} | {int(row['signal_count'])} | "
                f"{_fmt_pct(row['signal_hit_rate'])} | "
                f"{_fmt_return(row['signal_avg_return'])} | "
                f"{_fmt_return(row['baseline_avg_return'])} |"
            )
        lines.append("")
    return "\n".join(lines)
