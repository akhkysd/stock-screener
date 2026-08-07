import pytest

from src.data_sources.retry import RetryExhaustedError, call_with_backoff


def test_returns_result_on_first_success():
    sleeps = []
    result = call_with_backoff(lambda: 42, sleep=sleeps.append)
    assert result == 42
    assert sleeps == []


def test_retries_then_succeeds():
    calls = {"count": 0}

    def flaky():
        calls["count"] += 1
        if calls["count"] < 3:
            raise ValueError("transient")
        return "ok"

    sleeps = []
    result = call_with_backoff(flaky, max_retries=5, base_delay=1.0, sleep=sleeps.append)

    assert result == "ok"
    assert calls["count"] == 3
    assert len(sleeps) == 2
    # exponential backoff: second sleep should be roughly double the first
    assert sleeps[1] >= sleeps[0]


def test_raises_retry_exhausted_after_max_retries():
    def always_fails():
        raise ValueError("permanent")

    with pytest.raises(RetryExhaustedError):
        call_with_backoff(always_fails, max_retries=2, base_delay=0.01, sleep=lambda _: None)


def test_non_retriable_exception_propagates_immediately():
    calls = {"count": 0}

    def raises_type_error():
        calls["count"] += 1
        raise TypeError("not retriable")

    with pytest.raises(TypeError):
        call_with_backoff(
            raises_type_error,
            retriable_exceptions=(ValueError,),
            sleep=lambda _: None,
        )
    assert calls["count"] == 1


def test_delay_capped_at_max_delay():
    sleeps = []

    def always_fails():
        raise ValueError("boom")

    with pytest.raises(RetryExhaustedError):
        call_with_backoff(
            always_fails,
            max_retries=6,
            base_delay=10.0,
            max_delay=15.0,
            sleep=sleeps.append,
        )

    assert all(s <= 15.0 * 1.1 for s in sleeps)
