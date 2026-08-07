import numpy as np
import pandas as pd
import pytest

from src.backtest.backtest import (
    backtest_signal,
    compute_forward_returns,
    generate_backtest_markdown,
    low52w_near_signal,
    ma25_dip_signal,
    rsi_oversold_signal,
)


def _price_df(code: str, closes: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=len(closes), freq="B").strftime("%Y-%m-%d")
    return pd.DataFrame(
        {
            "code": code,
            "date": dates,
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
            "volume": 1000,
        }
    )


def test_compute_forward_returns_basic():
    df = _price_df("1", [100.0, 110.0, 121.0, 100.0, 100.0])

    result = compute_forward_returns(df, holding_days=(1, 2))

    row0 = result.iloc[0]
    assert row0["return_1d"] == pytest.approx(0.10)
    assert row0["return_2d"] == pytest.approx(0.21)
    # last rows have no future data -> NaN
    assert pd.isna(result.iloc[-1]["return_1d"])


def test_compute_forward_returns_handles_multiple_codes_independently():
    df = pd.concat(
        [_price_df("1", [100.0, 200.0]), _price_df("2", [100.0, 50.0])], ignore_index=True
    )

    result = compute_forward_returns(df, holding_days=(1,))
    result = result.set_index("code")

    assert result.loc["1"].iloc[0]["return_1d"] == pytest.approx(1.0)
    assert result.loc["2"].iloc[0]["return_1d"] == pytest.approx(-0.5)


def test_backtest_signal_computes_hit_rate_and_avg_return():
    closes = list(np.linspace(200, 100, 40)) + list(np.linspace(100, 150, 10))
    df = _price_df("1", closes)

    def always_signal(indicators_df):
        return indicators_df["rsi14"].notna()

    result = backtest_signal(df, always_signal, holding_days=(1, 5))

    assert set(result["holding_days"]) == {1, 5}
    row = result[result["holding_days"] == 1].iloc[0]
    assert row["signal_count"] > 0
    assert 0.0 <= row["signal_hit_rate"] <= 1.0


def test_backtest_signal_no_signal_matches_returns_none_stats():
    df = _price_df("1", list(np.linspace(100, 200, 40)))

    def never_signal(indicators_df):
        return indicators_df["rsi14"] < -1000

    result = backtest_signal(df, never_signal, holding_days=(1,))

    row = result.iloc[0]
    assert row["signal_count"] == 0
    assert row["signal_hit_rate"] is None


def test_rsi_oversold_signal_matches_low_rsi_rows():
    signal = rsi_oversold_signal(30.0)
    df = pd.DataFrame({"rsi14": [10.0, 50.0, 29.0, None]})
    assert list(signal(df)) == [True, False, True, False]


def test_ma25_dip_signal_matches_deep_negative_deviation():
    signal = ma25_dip_signal(-10.0)
    df = pd.DataFrame({"ma25_deviation": [-20.0, -5.0, -10.0, None]})
    assert list(signal(df)) == [True, False, True, False]


def test_low52w_near_signal_matches_small_deviation():
    signal = low52w_near_signal(20.0)
    df = pd.DataFrame({"low52w_deviation": [5.0, 30.0, 20.0, None]})
    assert list(signal(df)) == [True, False, True, False]


def test_generate_backtest_markdown_includes_signal_names_and_stats():
    results = {
        "RSI30以下": pd.DataFrame(
            [
                {
                    "holding_days": 5,
                    "signal_count": 10,
                    "signal_hit_rate": 0.6,
                    "signal_avg_return": 0.02,
                    "baseline_avg_return": 0.01,
                }
            ]
        ),
        "シグナルなし": pd.DataFrame(
            [
                {
                    "holding_days": 5,
                    "signal_count": 0,
                    "signal_hit_rate": None,
                    "signal_avg_return": None,
                    "baseline_avg_return": 0.01,
                }
            ]
        ),
    }

    report = generate_backtest_markdown(results)

    assert "RSI30以下" in report
    assert "60.0%" in report
    assert "シグナルなし" in report
    assert "N/A" in report
