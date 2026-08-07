import random
import time
from collections.abc import Callable

import requests

from src.data_sources.retry import call_with_backoff

BASE_URL = "https://api.edinet-fsa.go.jp/api/v2"
DOCUMENT_LIST_URL = f"{BASE_URL}/documents.json"
DOCUMENT_URL_TEMPLATE = f"{BASE_URL}/documents/{{doc_id}}"

MIN_REQUEST_INTERVAL_SECONDS = 3.0
MAX_REQUEST_INTERVAL_SECONDS = 5.0
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES = 5

DOCUMENT_LIST_TYPE = "2"
DOCUMENT_CSV_TYPE = "5"


def _default_get(url: str, params: dict, timeout: int) -> requests.Response:
    return requests.get(url, params=params, timeout=timeout)


class EdinetClient:
    def __init__(
        self,
        api_key: str,
        get_func: Callable[[str, dict, int], object] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        min_interval: float = MIN_REQUEST_INTERVAL_SECONDS,
        max_interval: float = MAX_REQUEST_INTERVAL_SECONDS,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        self._api_key = api_key
        self._get = get_func or _default_get
        self._sleep = sleep
        self._monotonic = monotonic
        self._min_interval = min_interval
        self._max_interval = max_interval
        self._max_retries = max_retries
        self._last_request_at: float | None = None

    def _throttle(self) -> None:
        now = self._monotonic()
        if self._last_request_at is not None:
            elapsed = now - self._last_request_at
            wait = random.uniform(self._min_interval, self._max_interval) - elapsed
            if wait > 0:
                self._sleep(wait)
        self._last_request_at = now

    def _request(self, url: str, params: dict):
        self._throttle()

        def do_request():
            response = self._get(url, params, REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response

        return call_with_backoff(do_request, max_retries=self._max_retries, sleep=self._sleep)

    def list_documents(self, date: str) -> list[dict]:
        response = self._request(
            DOCUMENT_LIST_URL,
            {"date": date, "type": DOCUMENT_LIST_TYPE, "Subscription-Key": self._api_key},
        )
        return response.json().get("results", [])

    def fetch_document_csv(self, doc_id: str) -> bytes:
        response = self._request(
            DOCUMENT_URL_TEMPLATE.format(doc_id=doc_id),
            {"type": DOCUMENT_CSV_TYPE, "Subscription-Key": self._api_key},
        )
        return response.content
