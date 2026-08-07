import io
import zipfile

from src.data_sources.edinet_csv_parser import parse_financial_csv

HEADER = ["要素ID", "項目名", "コンテキストID", "単位", "値"]


def _make_zip(
    rows: list[list[str]], member_name: str = "XBRL_TO_CSV/jpcrp030000-asr-001.csv"
) -> bytes:
    lines = ["\t".join(HEADER)] + ["\t".join(row) for row in rows]
    text = "\n".join(lines)
    csv_bytes = text.encode("utf-16")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(member_name, csv_bytes)
    return buf.getvalue()


def _sample_rows():
    return [
        [
            "jpcrp_cor:BasicEarningsLossPerShareSummaryOfBusinessResults",
            "1株当たり当期純利益又は1株当たり純損失（△）",
            "CurrentYearDuration",
            "円",
            "123.45",
        ],
        [
            "jpcrp_cor:NetAssetsPerShareSummaryOfBusinessResults",
            "1株当たり純資産額",
            "CurrentYearInstant",
            "円",
            "1500.5",
        ],
        [
            "jpcrp_cor:ProfitLossAttributableToOwnersOfParentSummaryOfBusinessResults",
            "親会社株主に帰属する当期純利益",
            "CurrentYearDuration",
            "千円",
            "987654",
        ],
        [
            "jpcrp_cor:NetAssetsSummaryOfBusinessResults",
            "純資産額",
            "CurrentYearInstant",
            "千円",
            "5000000",
        ],
        [
            "jpcrp_cor:TotalNumberOfIssuedSharesSummaryOfBusinessResults",
            "発行済株式総数",
            "CurrentYearInstant",
            "株",
            "8000000",
        ],
        # prior-year noise that should NOT be picked
        [
            "jpcrp_cor:ProfitLossAttributableToOwnersOfParentSummaryOfBusinessResults",
            "親会社株主に帰属する当期純利益",
            "Prior1YearDuration",
            "千円",
            "111111",
        ],
    ]


def test_parse_financial_csv_extracts_expected_fields():
    zip_bytes = _make_zip(_sample_rows())

    result = parse_financial_csv(zip_bytes)

    assert result["eps"] == 123.45
    assert result["bps"] == 1500.5
    assert result["net_income"] == 987654.0
    assert result["equity"] == 5000000.0
    assert result["shares_outstanding"] == 8000000.0


def test_parse_financial_csv_prefers_current_year_over_prior_year():
    zip_bytes = _make_zip(_sample_rows())
    result = parse_financial_csv(zip_bytes)
    assert result["net_income"] == 987654.0


def test_parse_financial_csv_handles_missing_field_gracefully():
    rows = [r for r in _sample_rows() if "発行済" not in r[1]]
    zip_bytes = _make_zip(rows)

    result = parse_financial_csv(zip_bytes)

    assert result["shares_outstanding"] is None
    assert result["eps"] == 123.45


def test_parse_financial_csv_handles_dash_as_missing_value():
    rows = _sample_rows()
    rows[0][4] = "－"
    zip_bytes = _make_zip(rows)

    result = parse_financial_csv(zip_bytes)

    assert result["eps"] is None


def test_parse_financial_csv_strips_comma_thousand_separators():
    rows = _sample_rows()
    rows[3][4] = "5,000,000"
    zip_bytes = _make_zip(rows)

    result = parse_financial_csv(zip_bytes)

    assert result["equity"] == 5000000.0
