import csv
import io
import zipfile

# EDINETの要素ID文字列は情報源により表記が一致しない（信頼度が中〜低）ため、
# 項目名（日本語ラベル）の部分一致を主な抽出方法とする。実データ入手後に要検証。
FIELD_PATTERNS: dict[str, tuple[list[str], list[str]]] = {
    "eps": (["1株当たり当期純利益"], []),
    "bps": (["1株当たり純資産"], []),
    "net_income": (["当期純利益"], ["1株当たり"]),
    "equity": (["純資産額"], ["1株当たり"]),
    "shares_outstanding": (["発行済株式総数", "発行済株式数"], []),
}

PREFERRED_CONTEXT_SUBSTRING = "CurrentYear"
EXCLUDED_CONTEXT_SUBSTRING = "NonConsolidated"

ITEM_NAME_COLUMN = "項目名"
CONTEXT_ID_COLUMN = "コンテキストID"
VALUE_COLUMN = "値"


def _matches(item_name: str, include: list[str], exclude: list[str]) -> bool:
    if not any(pattern in item_name for pattern in include):
        return False
    return not any(pattern in item_name for pattern in exclude)


def _select_best_row(rows: list[dict]) -> dict | None:
    if not rows:
        return None
    preferred = [
        r
        for r in rows
        if PREFERRED_CONTEXT_SUBSTRING in r.get(CONTEXT_ID_COLUMN, "")
        and EXCLUDED_CONTEXT_SUBSTRING not in r.get(CONTEXT_ID_COLUMN, "")
    ]
    return (preferred or rows)[0]


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = value.strip().replace(",", "")
    if cleaned in ("", "－", "-", "―"):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _read_csv_rows(csv_bytes: bytes) -> list[dict]:
    text = csv_bytes.decode("utf-16")
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    return list(reader)


def _find_financial_csv_member(zf: zipfile.ZipFile) -> str:
    candidates = [
        name
        for name in zf.namelist()
        if "XBRL_TO_CSV" in name and name.endswith(".csv") and "asr" in name.lower()
    ]
    if not candidates:
        candidates = [name for name in zf.namelist() if name.endswith(".csv")]
    if not candidates:
        raise ValueError("EDINET書類のZIP内にCSVファイルが見つかりません")
    return candidates[0]


def parse_financial_csv(zip_bytes: bytes) -> dict[str, float | None]:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        member = _find_financial_csv_member(zf)
        raw = zf.read(member)

    rows = _read_csv_rows(raw)

    result: dict[str, float | None] = {}
    for field, (include, exclude) in FIELD_PATTERNS.items():
        matches = [r for r in rows if _matches(r.get(ITEM_NAME_COLUMN, ""), include, exclude)]
        best = _select_best_row(matches)
        result[field] = _to_float(best.get(VALUE_COLUMN)) if best else None
    return result
