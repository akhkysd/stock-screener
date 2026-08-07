import pandas as pd

SECTOR_COLUMN = "sector"


def _grouped_zscore(df: pd.DataFrame, column: str) -> pd.Series:
    grouped = df.groupby(SECTOR_COLUMN)[column]
    mean = grouped.transform("mean")
    std = grouped.transform(lambda s: s.std(ddof=0))
    z = (df[column] - mean) / std
    return z.where(std != 0, 0.0)


def compute_fundamental_zscores(df: pd.DataFrame) -> pd.DataFrame:
    """PER/PBRは業種内で低いほど、ROEは高いほどスコアが高くなるようZスコア化する。

    yfinanceの`.info`由来の参考値を用いる暫定実装（フェーズ2でEDINET一次データにより検証）。
    """
    result = df.copy()
    result["per_score"] = -_grouped_zscore(df, "per")
    result["pbr_score"] = -_grouped_zscore(df, "pbr")
    result["roe_score"] = _grouped_zscore(df, "roe")
    return result
