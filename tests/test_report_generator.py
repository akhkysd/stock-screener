import pandas as pd

from src.report.report_generator import generate_markdown_report


def _ranking_df():
    return pd.DataFrame(
        [
            {
                "code": "1",
                "name": "銘柄A",
                "sector": "食品",
                "composite_score": 10.0,
                "sector_rank": 1,
                "sector_deviation": 65.0,
            },
            {
                "code": "2",
                "name": "銘柄B",
                "sector": "食品",
                "composite_score": 5.0,
                "sector_rank": 2,
                "sector_deviation": 50.0,
            },
            {
                "code": "3",
                "name": "銘柄C",
                "sector": "自動車",
                "composite_score": 8.0,
                "sector_rank": 1,
                "sector_deviation": 70.0,
            },
        ]
    )


def test_report_includes_date_header():
    report = generate_markdown_report("2026-08-07", _ranking_df(), missing_codes=[])
    assert "2026-08-07" in report


def test_report_groups_by_sector():
    report = generate_markdown_report("2026-08-07", _ranking_df(), missing_codes=[])
    assert "食品" in report
    assert "自動車" in report


def test_report_orders_by_sector_rank():
    report = generate_markdown_report("2026-08-07", _ranking_df(), missing_codes=[])
    assert report.index("銘柄A") < report.index("銘柄B")


def test_report_limits_to_top_n_per_sector():
    df = pd.DataFrame(
        [
            {
                "code": str(i),
                "name": f"銘柄{i}",
                "sector": "食品",
                "composite_score": float(100 - i),
                "sector_rank": i,
                "sector_deviation": 50.0,
            }
            for i in range(1, 6)
        ]
    )

    report = generate_markdown_report("2026-08-07", df, missing_codes=[], top_n=2)

    assert "銘柄1" in report
    assert "銘柄2" in report
    assert "銘柄3" not in report


def test_report_lists_missing_codes():
    report = generate_markdown_report("2026-08-07", _ranking_df(), missing_codes=["9999", "8888"])
    assert "9999" in report
    assert "8888" in report
    assert "データ欠損銘柄" in report


def test_report_omits_missing_section_when_empty():
    report = generate_markdown_report("2026-08-07", _ranking_df(), missing_codes=[])
    assert "データ欠損銘柄" not in report


def test_report_handles_empty_ranking_df():
    empty = pd.DataFrame(
        columns=["code", "name", "sector", "composite_score", "sector_rank", "sector_deviation"]
    )
    report = generate_markdown_report("2026-08-07", empty, missing_codes=[])
    assert "2026-08-07" in report
