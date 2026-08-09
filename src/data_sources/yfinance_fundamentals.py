import math
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import pandas as pd
import yfinance as yf

from src.data_sources.retry import RetryExhaustedError, call_with_backoff

MIN_REQUEST_INTERVAL_SECONDS = 1.0
MAX_REQUEST_INTERVAL_SECONDS = 3.0
MAX_RETRIES = 5

FUNDAMENTALS_COLUMNS = ["code", "per", "pbr", "roe"]


@dataclass
class FundamentalsFetchResult:
    fundamentals: pd.DataFrame
    failed_codes: list[str] = field(default_factory=list)


def _to_ticker(code: str) -> str:
    return f"{code}.T"


def _default_info_provider(ticker: str) -> dict:
    return yf.Ticker(ticker).info


def _coerce_float(value: object) -> float | None:
    """yfinanceの.infoは銘柄によって非数値（文字列プレースホルダ等）を返すことがある。"""
    if value is None:
        return None
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


class YFinanceFundamentalsClient:
    def __init__(
        self,
        info_provider: Callable[[str], dict] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        min_interval: float = MIN_REQUEST_INTERVAL_SECONDS,
        max_interval: float = MAX_REQUEST_INTERVAL_SECONDS,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        self._info_provider = info_provider or _default_info_provider
        self._sleep = sleep
        self._min_interval = min_interval
        self._max_interval = max_interval
        self._max_retries = max_retries

    def fetch_fundamentals(self, codes: list[str]) -> FundamentalsFetchResult:
        rows = []
        failed: list[str] = []

        for index, code in enumerate(codes):
            ticker = _to_ticker(code)

            def fetch_info(ticker: str = ticker) -> dict:
                return self._info_provider(ticker)

            try:
                info = call_with_backoff(
                    fetch_info,
                    max_retries=self._max_retries,
                    sleep=self._sleep,
                )
            except RetryExhaustedError:
                failed.append(code)
            else:
                rows.append(
                    {
                        "code": code,
                        "per": _coerce_float(info.get("trailingPE")),
                        "pbr": _coerce_float(info.get("priceToBook")),
                        "roe": _coerce_float(info.get("returnOnEquity")),
                    }
                )

            if index < len(codes) - 1:
                self._sleep(random.uniform(self._min_interval, self._max_interval))

        fundamentals = pd.DataFrame(rows, columns=FUNDAMENTALS_COLUMNS)
        for column in ("per", "pbr", "roe"):
            fundamentals[column] = fundamentals[column].astype(float)
        return FundamentalsFetchResult(fundamentals=fundamentals, failed_codes=failed)
