import numpy as np
import pandas as pd

from src.scoring.technical_score import compute_technical_indicators


def _price_df(code: str, closes: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=len(closes), freq="B")
    return pd.DataFrame(
        {
            "code": code,
            "date": dates.strftime("%Y-%m-%d"),
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
            "volume": [1000] * len(closes),
        }
    )


def test_rsi14_is_high_for_steadily_rising_prices():
    closes = list(np.linspace(100, 200, 40))
    df = _price_df("1", closes)

    result = compute_technical_indicators(df)

    last_rsi = result["rsi14"].iloc[-1]
    assert last_rsi > 70


def test_rsi14_is_low_for_steadily_falling_prices():
    closes = list(np.linspace(200, 100, 40))
    df = _price_df("1", closes)

    result = compute_technical_indicators(df)

    last_rsi = result["rsi14"].iloc[-1]
    assert last_rsi < 30


def test_rsi14_is_nan_when_insufficient_history():
    closes = [100.0, 101.0, 102.0]
    df = _price_df("1", closes)

    result = compute_technical_indicators(df)

    assert result["rsi14"].isna().all()


def test_ma_deviation_is_negative_when_price_below_moving_average():
    closes = [100.0] * 30 + [80.0]
    df = _price_df("1", closes)

    result = compute_technical_indicators(df)

    assert result["ma25_deviation"].iloc[-1] < 0


def test_ma_deviation_is_positive_when_price_above_moving_average():
    closes = [100.0] * 30 + [130.0]
    df = _price_df("1", closes)

    result = compute_technical_indicators(df)

    assert result["ma25_deviation"].iloc[-1] > 0


def test_low52w_deviation_is_zero_at_the_low_itself():
    closes = [150.0] * 100 + [100.0]
    df = _price_df("1", closes)

    result = compute_technical_indicators(df)

    assert result["low52w_deviation"].iloc[-1] == 0.0


def test_low52w_deviation_positive_above_the_low():
    closes = [100.0] * 100 + [110.0]
    df = _price_df("1", closes)

    result = compute_technical_indicators(df)

    last = result["low52w_deviation"].iloc[-1]
    assert last > 0
    assert last == 10.0


def test_handles_multiple_codes_independently():
    df1 = _price_df("1", list(np.linspace(100, 200, 40)))
    df2 = _price_df("2", list(np.linspace(200, 100, 40)))
    combined = pd.concat([df1, df2], ignore_index=True)

    result = compute_technical_indicators(combined)

    assert set(result["code"].unique()) == {"1", "2"}
    assert len(result) == len(combined)
