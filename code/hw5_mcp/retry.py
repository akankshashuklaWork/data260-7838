"""Deterministic bounded retry and fault-injection helpers for HW5 Part 3."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

T = TypeVar("T")


class TransientOperationError(RuntimeError):
    pass


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 3
    timeout_seconds: float = 0.25
    backoff_seconds: float = 0.01


@dataclass
class AttemptResult:
    success: bool
    attempts: int
    value: T | None = None
    error: str | None = None


class FaultInjector:
    def __init__(self, rate: float, seed: int) -> None:
        if not 0 <= rate <= 1:
            raise ValueError("failure rate must be between 0 and 1")
        self.rate = rate
        self.rng = random.Random(seed)

    def fail_this_call(self) -> bool:
        return self.rng.random() < self.rate


def run_with_retry(
    operation: Callable[[], T],
    policy: RetryPolicy,
    injector: FaultInjector | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> AttemptResult[T]:
    """Run an operation with timeout-aware, bounded exponential backoff.

    The injector is deliberately checked per attempt, making retry behavior
    visible in the raw experiment records.
    """

    attempts = 0
    last_error = "operation failed"
    for retry_number in range(policy.max_retries + 1):
        attempts += 1
        started = time.monotonic()
        try:
            if injector and injector.fail_this_call():
                raise TransientOperationError("injected transient failure")
            value = operation()
            if time.monotonic() - started > policy.timeout_seconds:
                raise TimeoutError("operation timeout")
            return AttemptResult(True, attempts, value=value)
        except (TransientOperationError, TimeoutError, OSError) as exc:
            last_error = str(exc)
            if retry_number >= policy.max_retries:
                break
            sleep(policy.backoff_seconds * (2**retry_number))
    return AttemptResult(False, attempts, error=last_error)

