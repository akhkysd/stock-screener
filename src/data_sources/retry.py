import random
import time
from collections.abc import Callable


class RetryExhaustedError(Exception):
    pass


def call_with_backoff[T](
    func: Callable[[], T],
    *,
    max_retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retriable_exceptions: tuple[type[Exception], ...] = (Exception,),
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    attempt = 0
    while True:
        try:
            return func()
        except retriable_exceptions as exc:
            attempt += 1
            if attempt > max_retries:
                raise RetryExhaustedError(f"exceeded {max_retries} retries") from exc
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            delay += random.uniform(0, delay * 0.1)
            sleep(delay)
