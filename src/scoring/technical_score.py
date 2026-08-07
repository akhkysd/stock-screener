import pandas as pd

RSI_PERIOD = 14
MA_SHORT_WINDOW = 25
MA_LONG_WINDOW = 75
LOW52W_WINDOW_DAYS = 252


def _rsi14(closes: pd.Series) -> pd.Series:
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / RSI_PERIOD, adjust=False, min_periods=RSI_PERIOD).mean()
    avg_loss = loss.ewm(alpha=1 / RSI_PERIOD, adjust=False, min_periods=RSI_PERIOD).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _ma_deviation(closes: pd.Series, window: int) -> pd.Series:
    ma = closes.rolling(window=window, min_periods=window).mean()
    return (closes - ma) / ma * 100


def _low52w_deviation(closes: pd.Series) -> pd.Series:
    low52w = closes.rolling(window=LOW52W_WINDOW_DAYS, min_periods=1).min()
    return (closes - low52w) / low52w * 100


def _compute_for_one_code(group: pd.DataFrame) -> pd.DataFrame:
    group = group.sort_values("date")
    closes = group["close"]
    return pd.DataFrame(
        {
            "code": group["code"].to_numpy(),
            "date": group["date"].to_numpy(),
            "rsi14": _rsi14(closes).to_numpy(),
            "ma25_deviation": _ma_deviation(closes, MA_SHORT_WINDOW).to_numpy(),
            "ma75_deviation": _ma_deviation(closes, MA_LONG_WINDOW).to_numpy(),
            "low52w_deviation": _low52w_deviation(closes).to_numpy(),
        }
    )


def compute_technical_indicators(price_df: pd.DataFrame) -> pd.DataFrame:
    groups = [_compute_for_one_code(group) for _, group in price_df.groupby("code", sort=False)]
    return pd.concat(groups, ignore_index=True)
