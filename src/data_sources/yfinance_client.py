import random
import time
from collections.abc import Callable, Iterator

import pandas as pd
import yfinance as yf

from src.data_sources.base import PRICE_COLUMNS, PriceFetchResult
from src.data_sources.retry import RetryExhaustedError, call_with_backoff

BATCH_SIZE = 80
MIN_BATCH_PAUSE_SECONDS = 20.0
MAX_BATCH_PAUSE_SECONDS = 40.0
MAX_RETRIES = 5


def _to_ticker(code: str) -> str:
    return f"{code}.T"


def _batched(codes: list[str], size: int) -> Iterator[list[str]]:
    for i in range(0, len(codes), size):
        yield codes[i : i + size]


def _reshape_long(raw: pd.DataFrame, codes: list[str]) -> pd.DataFrame:
    rows = []
    tickers_present = set(raw.columns.get_level_values(0))
    for code in codes:
        ticker = _to_ticker(code)
        if ticker not in tickers_present:
            continue
        sub = raw[ticker]
        for idx, row in sub.iterrows():
            close = row.get("Close")
            if pd.isna(close):
                continue
            rows.append(
                {
                    "code": code,
                    "date": idx.strftime("%Y-%m-%d"),
                    "open": row.get("Open"),
                    "high": row.get("High"),
                    "low": row.get("Low"),
                    "close": close,
                    "volume": row.get("Volume"),
                }
            )
    return pd.DataFrame(rows, columns=PRICE_COLUMNS)


class YFinancePriceClient:
    def __init__(
        self,
        batch_size: int = BATCH_SIZE,
        sleep: Callable[[float], None] = time.sleep,
        downloader: Callable[..., pd.DataFrame] | None = None,
        min_batch_pause: float = MIN_BATCH_PAUSE_SECONDS,
        max_batch_pause: float = MAX_BATCH_PAUSE_SECONDS,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        self._batch_size = batch_size
        self._sleep = sleep
        self._downloader = downloader or yf.download
        self._min_batch_pause = min_batch_pause
        self._max_batch_pause = max_batch_pause
        self._max_retries = max_retries

    def fetch_daily_prices(self, codes: list[str], start: str, end: str) -> PriceFetchResult:
        batches = list(_batched(codes, self._batch_size))
        all_frames: list[pd.DataFrame] = []
        failed: list[str] = []

        for batch_index, batch_codes in enumerate(batches):
            tickers = [_to_ticker(c) for c in batch_codes]

            def download(tickers: list[str] = tickers) -> pd.DataFrame:
                return self._downloader(
                    tickers,
                    start=start,
                    end=end,
                    group_by="ticker",
                    auto_adjust=False,
                    progress=False,
                    threads=False,
                )

            try:
                raw = call_with_backoff(
                    download,
                    max_retries=self._max_retries,
                    sleep=self._sleep,
                )
            except RetryExhaustedError:
                failed.extend(batch_codes)
            else:
                long_df = _reshape_long(raw, batch_codes)
                fetched_codes = set(long_df["code"].unique())
                failed.extend(c for c in batch_codes if c not in fetched_codes)
                all_frames.append(long_df)

            if batch_index < len(batches) - 1:
                self._sleep(random.uniform(self._min_batch_pause, self._max_batch_pause))

        prices = (
            pd.concat(all_frames, ignore_index=True)
            if all_frames
            else pd.DataFrame(columns=PRICE_COLUMNS)
        )
        return PriceFetchResult(prices=prices, failed_codes=failed)
