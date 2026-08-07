import pandas as pd

from src.sector.sector_aggregation import compute_sector_ranking


def test_rank_1_is_the_highest_composite_score_within_sector():
    df = pd.DataFrame(
        [
            {"code": "1", "sector": "A", "composite_score": 5.0},
            {"code": "2", "sector": "A", "composite_score": 10.0},
            {"code": "3", "sector": "A", "composite_score": 1.0},
        ]
    )

    result = compute_sector_ranking(df)
    result = result.set_index("code")

    assert result.loc["2", "sector_rank"] == 1
    assert result.loc["1", "sector_rank"] == 2
    assert result.loc["3", "sector_rank"] == 3


def test_ranking_is_independent_per_sector():
    df = pd.DataFrame(
        [
            {"code": "1", "sector": "A", "composite_score": 100.0},
            {"code": "2", "sector": "B", "composite_score": 1.0},
        ]
    )

    result = compute_sector_ranking(df).set_index("code")

    assert result.loc["1", "sector_rank"] == 1
    assert result.loc["2", "sector_rank"] == 1


def test_sector_deviation_is_50_for_average_score():
    df = pd.DataFrame(
        [
            {"code": "1", "sector": "A", "composite_score": 5.0},
            {"code": "2", "sector": "A", "composite_score": 10.0},
            {"code": "3", "sector": "A", "composite_score": 0.0},
        ]
    )

    result = compute_sector_ranking(df).set_index("code")

    assert result.loc["2", "sector_deviation"] > 50.0
    assert result.loc["3", "sector_deviation"] < 50.0


def test_single_member_sector_gets_neutral_deviation():
    df = pd.DataFrame([{"code": "1", "sector": "A", "composite_score": 42.0}])

    result = compute_sector_ranking(df)

    assert result.iloc[0]["sector_deviation"] == 50.0
    assert result.iloc[0]["sector_rank"] == 1


def test_ties_get_the_same_rank():
    df = pd.DataFrame(
        [
            {"code": "1", "sector": "A", "composite_score": 5.0},
            {"code": "2", "sector": "A", "composite_score": 5.0},
            {"code": "3", "sector": "A", "composite_score": 1.0},
        ]
    )

    result = compute_sector_ranking(df).set_index("code")

    assert result.loc["1", "sector_rank"] == result.loc["2", "sector_rank"] == 1
    assert result.loc["3", "sector_rank"] == 3
