import pandas as pd

from src.scoring.fundamental_score import compute_fundamental_zscores


def _df():
    return pd.DataFrame(
        [
            {"code": "1", "sector": "A", "per": 10.0, "pbr": 1.0, "roe": 5.0},
            {"code": "2", "sector": "A", "per": 20.0, "pbr": 2.0, "roe": 10.0},
            {"code": "3", "sector": "A", "per": 30.0, "pbr": 3.0, "roe": 15.0},
            {"code": "4", "sector": "B", "per": 5.0, "pbr": 0.5, "roe": 20.0},
            {"code": "5", "sector": "B", "per": 15.0, "pbr": 1.5, "roe": 10.0},
        ]
    )


def test_lower_per_gets_higher_score_within_sector():
    result = compute_fundamental_zscores(_df())
    sector_a = result[result["sector"] == "A"].set_index("code")
    assert sector_a.loc["1", "per_score"] > sector_a.loc["2", "per_score"]
    assert sector_a.loc["2", "per_score"] > sector_a.loc["3", "per_score"]


def test_lower_pbr_gets_higher_score_within_sector():
    result = compute_fundamental_zscores(_df())
    sector_a = result[result["sector"] == "A"].set_index("code")
    assert sector_a.loc["1", "pbr_score"] > sector_a.loc["3", "pbr_score"]


def test_higher_roe_gets_higher_score_within_sector():
    result = compute_fundamental_zscores(_df())
    sector_a = result[result["sector"] == "A"].set_index("code")
    assert sector_a.loc["3", "roe_score"] > sector_a.loc["1", "roe_score"]


def test_scoring_is_relative_to_sector_not_global():
    result = compute_fundamental_zscores(_df())
    # code 4 (sector B, PER=5, lowest overall) should score highest in its own sector,
    # independent of sector A's distribution
    sector_b = result[result["sector"] == "B"].set_index("code")
    assert sector_b.loc["4", "per_score"] > sector_b.loc["5", "per_score"]


def test_missing_values_do_not_crash_and_yield_nan_score():
    df = _df()
    df.loc[df["code"] == "2", "per"] = None
    result = compute_fundamental_zscores(df)
    row = result[result["code"] == "2"].iloc[0]
    assert pd.isna(row["per_score"])


def test_single_member_sector_yields_neutral_score():
    df = pd.DataFrame([{"code": "9", "sector": "C", "per": 12.0, "pbr": 1.2, "roe": 8.0}])
    result = compute_fundamental_zscores(df)
    assert result.iloc[0]["per_score"] == 0.0
