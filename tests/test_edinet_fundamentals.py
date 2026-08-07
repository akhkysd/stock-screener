import pandas as pd
import pytest

from src.data_sources.edinet_fundamentals import (
    compute_verified_fundamentals,
    filter_target_documents,
    is_target_document,
    update_fundamentals_from_documents,
)
from src.db import apply_schema, get_connection


def test_is_target_document_matches_sec_code_prefix_and_form_code():
    doc = {"secCode": "72030", "formCode": "030000"}
    assert is_target_document(doc, {"7203"})
    assert not is_target_document(doc, {"1301"})


def test_is_target_document_rejects_non_target_form_code():
    doc = {"secCode": "72030", "formCode": "999999"}
    assert not is_target_document(doc, {"7203"})


def test_filter_target_documents():
    docs = [
        {"secCode": "72030", "formCode": "030000", "docID": "A"},
        {"secCode": "13010", "formCode": "030000", "docID": "B"},
        {"secCode": "99990", "formCode": "030000", "docID": "C"},
    ]
    result = filter_target_documents(docs, {"7203", "1301"})
    assert {d["docID"] for d in result} == {"A", "B"}


class FakeClient:
    def __init__(self, docs, csv_bytes_by_doc_id):
        self._docs = docs
        self._csv_bytes = csv_bytes_by_doc_id

    def list_documents(self, date):
        return self._docs

    def fetch_document_csv(self, doc_id):
        if doc_id not in self._csv_bytes:
            raise RuntimeError("not found")
        return self._csv_bytes[doc_id]


@pytest.fixture
def conn():
    c = get_connection(":memory:")
    apply_schema(c)
    return c


def test_update_fundamentals_from_documents_upserts_parsed_values(conn):
    docs = [{"secCode": "72030", "formCode": "030000", "docID": "DOC1", "periodEnd": "2026-03-31"}]
    client = FakeClient(docs, {"DOC1": b"zip-bytes"})

    def fake_parser(zip_bytes):
        assert zip_bytes == b"zip-bytes"
        return {
            "eps": 100.0,
            "bps": 1000.0,
            "net_income": 500.0,
            "equity": 5000.0,
            "shares_outstanding": 10.0,
        }

    result = update_fundamentals_from_documents(
        conn,
        client,
        date="2026-08-07",
        target_codes={"7203"},
        updated_at="2026-08-07",
        csv_parser=fake_parser,
    )

    assert result.updated_codes == ["7203"]
    assert result.failed_doc_ids == []

    row = conn.execute("SELECT * FROM fundamentals WHERE code = '7203'").fetchone()
    assert row["eps"] == 100.0
    assert row["fiscal_period"] == "2026-03-31"


def test_update_fundamentals_from_documents_records_failed_doc_without_aborting(conn):
    docs = [
        {"secCode": "72030", "formCode": "030000", "docID": "DOC-BAD", "periodEnd": "2026-03-31"},
        {"secCode": "13010", "formCode": "030000", "docID": "DOC-OK", "periodEnd": "2026-03-31"},
    ]
    client = FakeClient(docs, {"DOC-OK": b"zip-bytes"})

    def fake_parser(zip_bytes):
        return {"eps": 1.0, "bps": 1.0, "net_income": 1.0, "equity": 1.0, "shares_outstanding": 1.0}

    result = update_fundamentals_from_documents(
        conn,
        client,
        date="2026-08-07",
        target_codes={"7203", "1301"},
        updated_at="2026-08-07",
        csv_parser=fake_parser,
    )

    assert result.updated_codes == ["1301"]
    assert result.failed_doc_ids == ["DOC-BAD"]


def test_compute_verified_fundamentals_prefers_edinet_over_yfinance():
    edinet_df = pd.DataFrame(
        [{"code": "7203", "eps": 100.0, "bps": 1000.0, "net_income": 500.0, "equity": 5000.0}]
    )
    latest_prices = pd.DataFrame([{"code": "7203", "close": 2000.0}])
    yfinance_df = pd.DataFrame(
        [
            {"code": "7203", "per": 999.0, "pbr": 999.0, "roe": 999.0},
            {"code": "6758", "per": 20.0, "pbr": 2.0, "roe": 0.1},
        ]
    )

    result = compute_verified_fundamentals(edinet_df, latest_prices, yfinance_df)
    result = result.set_index("code")

    assert result.loc["7203", "per"] == pytest.approx(20.0)  # 2000/100
    assert result.loc["7203", "pbr"] == pytest.approx(2.0)  # 2000/1000
    assert result.loc["7203", "roe"] == pytest.approx(0.1)  # 500/5000
    assert result.loc["7203", "source"] == "edinet"


def test_compute_verified_fundamentals_falls_back_to_yfinance_when_no_edinet_data():
    edinet_df = pd.DataFrame(columns=["code", "eps", "bps", "net_income", "equity"])
    latest_prices = pd.DataFrame(columns=["code", "close"])
    yfinance_df = pd.DataFrame([{"code": "6758", "per": 20.0, "pbr": 2.0, "roe": 0.1}])

    result = compute_verified_fundamentals(edinet_df, latest_prices, yfinance_df)

    assert len(result) == 1
    assert result.iloc[0]["code"] == "6758"
    assert result.iloc[0]["source"] == "yfinance"
