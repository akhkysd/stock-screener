from dataclasses import dataclass, field
from typing import Protocol

import pandas as pd

PRICE_COLUMNS = ["code", "date", "open", "high", "low", "close", "volume"]


@dataclass
class PriceFetchResult:
    prices: pd.DataFrame
    failed_codes: list[str] = field(default_factory=list)


class PriceDataSource(Protocol):
    def fetch_daily_prices(self, codes: list[str], start: str, end: str) -> PriceFetchResult: ...
