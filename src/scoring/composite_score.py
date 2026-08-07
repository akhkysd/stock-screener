import tomllib
from pathlib import Path

import pandas as pd

DEFAULT_WEIGHTS_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "weights.toml"


def load_weights(path: Path = DEFAULT_WEIGHTS_PATH) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def _clip_positive(series: pd.Series) -> pd.Series:
    return series.clip(lower=0).fillna(0)


def _compute_technical_signal_scores(technical_df: pd.DataFrame, weights: dict) -> pd.DataFrame:
    thresholds = weights["thresholds"]
    tech_weights = weights["weights"]["technical"]

    if technical_df.empty:
        return pd.DataFrame(columns=["code", "date", "technical_score"])

    rsi_score = _clip_positive(thresholds["rsi_oversold"] - technical_df["rsi14"])
    ma25_score = _clip_positive(
        thresholds["ma25_deviation_threshold"] - technical_df["ma25_deviation"]
    )
    ma75_score = _clip_positive(
        thresholds["ma75_deviation_threshold"] - technical_df["ma75_deviation"]
    )
    low52w_score = _clip_positive(
        thresholds["low52w_deviation_threshold"] - technical_df["low52w_deviation"]
    )

    technical_score = (
        rsi_score * tech_weights["rsi"]
        + ma25_score * tech_weights["ma25"]
        + ma75_score * tech_weights["ma75"]
        + low52w_score * tech_weights["low52w"]
    )
    return pd.DataFrame(
        {
            "code": technical_df["code"],
            "date": technical_df["date"],
            "technical_score": technical_score,
        }
    )


def compute_composite_scores(
    fundamentals_df: pd.DataFrame, technical_df: pd.DataFrame, weights: dict
) -> pd.DataFrame:
    fund_weights = weights["weights"]["fundamental"]
    comp_weights = weights["weights"]["composite"]

    fundamental_composite = (
        fundamentals_df["per_score"] * fund_weights["per"]
        + fundamentals_df["pbr_score"] * fund_weights["pbr"]
        + fundamentals_df["roe_score"] * fund_weights["roe"]
    )
    result = fundamentals_df.copy()
    result["fundamental_composite"] = fundamental_composite

    technical_scores = _compute_technical_signal_scores(technical_df, weights)
    result = result.merge(technical_scores[["code", "technical_score"]], on="code", how="left")
    result["technical_score"] = result["technical_score"].fillna(0.0)

    result["composite_score"] = (
        comp_weights["fundamental"] * result["fundamental_composite"]
        + comp_weights["technical"] * result["technical_score"]
    )
    return result
