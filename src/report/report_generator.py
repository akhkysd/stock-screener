import pandas as pd

DEFAULT_TOP_N = 10


def generate_markdown_report(
    date: str,
    ranking_df: pd.DataFrame,
    missing_codes: list[str],
    top_n: int = DEFAULT_TOP_N,
) -> str:
    lines = [f"# 国内割安・底値株 業種別デイリーレポート（{date}）", ""]

    if ranking_df.empty:
        lines.append("対象銘柄がありません。")
    else:
        for sector in sorted(ranking_df["sector"].unique()):
            sector_df = (
                ranking_df[ranking_df["sector"] == sector].sort_values("sector_rank").head(top_n)
            )
            lines.append(f"## {sector}")
            lines.append("")
            lines.append("| 順位 | コード | 銘柄名 | 総合スコア | 業種内偏差値 |")
            lines.append("|---|---|---|---|---|")
            for _, row in sector_df.iterrows():
                lines.append(
                    f"| {row['sector_rank']} | {row['code']} | {row['name']} | "
                    f"{row['composite_score']:.2f} | {row['sector_deviation']:.1f} |"
                )
            lines.append("")

    if missing_codes:
        lines.append("## データ欠損銘柄")
        lines.append("")
        lines.append("以下の銘柄は本日データを取得できなかったため、集計から除外されています。")
        lines.append("")
        lines.append(", ".join(missing_codes))
        lines.append("")

    return "\n".join(lines)
