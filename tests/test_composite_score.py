import pandas as pd
import pytest

from src.scoring.composite_score import compute_composite_scores, load_weights

THRESHOLDS = {
    "rsi_oversold": 30.0,
    "ma25_deviation_threshold": -10.0,
    "ma75_deviation_threshold": -10.0,
    "low52w_deviation_threshold": 20.0,
}
TECH_WEIGHTS = {"rsi": 1.0, "ma25": 1.0, "ma75": 1.0, "low52w": 1.0}
FUND_WEIGHTS = {"per": 1.0, "pbr": 1.0, "roe": 1.0}
COMPOSITE_WEIGHTS = {"fundamental": 0.5, "technical": 0.5}


def _weights():
    return {
        "thresholds": THRESHOLDS,
        "weights": {
            "fundamental": FUND_WEIGHTS,
            "technical": TECH_WEIGHTS,
            "composite": COMPOSITE_WEIGHTS,
        },
    }


def test_load_weights_reads_real_config_file():
    weights = load_weights()
    assert "thresholds" in weights
    assert weights["weights"]["composite"]["fundamental"] + weights["weights"]["composite"][
        "technical"
    ] == pytest.approx(1.0)


def test_oversold_rsi_increases_technical_score():
    fundamentals = pd.DataFrame(
        [{"code": "1", "sector": "A", "per_score": 0.0, "pbr_score": 0.0, "roe_score": 0.0}]
    )
    oversold = pd.DataFrame(
        [
            {
                "code": "1",
                "date": "2026-08-07",
                "rsi14": 10.0,
                "ma25_deviation": 0.0,
                "ma75_deviation": 0.0,
                "low52w_deviation": 100.0,
            }
        ]
    )
    neutral = pd.DataFrame(
        [
            {
                "code": "1",
                "date": "2026-08-07",
                "rsi14": 50.0,
                "ma25_deviation": 0.0,
                "ma75_deviation": 0.0,
                "low52w_deviation": 100.0,
            }
        ]
    )

    oversold_result = compute_composite_scores(fundamentals, oversold, _weights())
    neutral_result = compute_composite_scores(fundamentals, neutral, _weights())

    assert oversold_result.iloc[0]["composite_score"] > neutral_result.iloc[0]["composite_score"]


def test_deep_below_ma25_increases_technical_score():
    fundamentals = pd.DataFrame(
        [{"code": "1", "sector": "A", "per_score": 0.0, "pbr_score": 0.0, "roe_score": 0.0}]
    )
    below = pd.DataFrame(
        [
            {
                "code": "1",
                "date": "2026-08-07",
                "rsi14": 50.0,
                "ma25_deviation": -20.0,
                "ma75_deviation": 0.0,
                "low52w_deviation": 100.0,
            }
        ]
    )
    at_ma = pd.DataFrame(
        [
            {
                "code": "1",
                "date": "2026-08-07",
                "rsi14": 50.0,
                "ma25_deviation": 0.0,
                "ma75_deviation": 0.0,
                "low52w_deviation": 100.0,
            }
        ]
    )

    below_result = compute_composite_scores(fundamentals, below, _weights())
    at_ma_result = compute_composite_scores(fundamentals, at_ma, _weights())

    assert below_result.iloc[0]["composite_score"] > at_ma_result.iloc[0]["composite_score"]


def test_near_52w_low_increases_technical_score():
    fundamentals = pd.DataFrame(
        [{"code": "1", "sector": "A", "per_score": 0.0, "pbr_score": 0.0, "roe_score": 0.0}]
    )
    near_low = pd.DataFrame(
        [
            {
                "code": "1",
                "date": "2026-08-07",
                "rsi14": 50.0,
                "ma25_deviation": 0.0,
                "ma75_deviation": 0.0,
                "low52w_deviation": 1.0,
            }
        ]
    )
    far_from_low = pd.DataFrame(
        [
            {
                "code": "1",
                "date": "2026-08-07",
                "rsi14": 50.0,
                "ma25_deviation": 0.0,
                "ma75_deviation": 0.0,
                "low52w_deviation": 100.0,
            }
        ]
    )

    near_result = compute_composite_scores(fundamentals, near_low, _weights())
    far_result = compute_composite_scores(fundamentals, far_from_low, _weights())

    assert near_result.iloc[0]["composite_score"] > far_result.iloc[0]["composite_score"]


def test_fundamental_score_contributes_to_composite():
    good_fundamentals = pd.DataFrame(
        [{"code": "1", "sector": "A", "per_score": 2.0, "pbr_score": 2.0, "roe_score": 2.0}]
    )
    bad_fundamentals = pd.DataFrame(
        [{"code": "1", "sector": "A", "per_score": -2.0, "pbr_score": -2.0, "roe_score": -2.0}]
    )
    technical = pd.DataFrame(
        [
            {
                "code": "1",
                "date": "2026-08-07",
                "rsi14": 50.0,
                "ma25_deviation": 0.0,
                "ma75_deviation": 0.0,
                "low52w_deviation": 100.0,
            }
        ]
    )

    good_result = compute_composite_scores(good_fundamentals, technical, _weights())
    bad_result = compute_composite_scores(bad_fundamentals, technical, _weights())

    assert good_result.iloc[0]["composite_score"] > bad_result.iloc[0]["composite_score"]


def test_missing_technical_row_does_not_crash():
    fundamentals = pd.DataFrame(
        [{"code": "1", "sector": "A", "per_score": 1.0, "pbr_score": 1.0, "roe_score": 1.0}]
    )
    technical = pd.DataFrame(
        columns=["code", "date", "rsi14", "ma25_deviation", "ma75_deviation", "low52w_deviation"]
    )

    result = compute_composite_scores(fundamentals, technical, _weights())

    assert len(result) == 1
    assert pd.notna(result.iloc[0]["composite_score"])
