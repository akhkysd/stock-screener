import pandas as pd

SCORE_COLUMN = "composite_score"
SECTOR_COLUMN = "sector"


def compute_sector_ranking(df: pd.DataFrame) -> pd.DataFrame:
    """業種内での順位・偏差値（平均50・標準偏差10換算）を算出する。"""
    result = df.copy()
    grouped = result.groupby(SECTOR_COLUMN)[SCORE_COLUMN]

    result["sector_rank"] = grouped.rank(method="min", ascending=False).astype("Int64")

    mean = grouped.transform("mean")
    std = grouped.transform(lambda s: s.std(ddof=0))
    deviation = 50 + 10 * (result[SCORE_COLUMN] - mean) / std
    result["sector_deviation"] = deviation.where(std != 0, 50.0)
    return result
