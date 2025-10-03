"""
Exponential Backoff Implementation

Production-ready backoff strategies with jitter and customization.
"""

import random
import time
import math
from abc import ABC, abstractmethod
from enum import Enum
from typing import Iterator
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class BackoffStrategy(Enum):
    """Backoff strategy types"""
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"
    FIBONACCI = "fibonacci"


@dataclass
class BackoffConfig:
    """Backoff configuration"""
    base_delay: float = 1.0          # Base delay in seconds
    max_delay: float = 60.0          # Maximum delay in seconds
    multiplier: float = 2.0          # Exponential multiplier
    jitter: bool = True              # Add random jitter
    jitter_ratio: float = 0.1        # Jitter ratio (0.0 - 1.0)
    strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL


class BackoffCalculator(ABC):
    """Abstract base for backoff calculators"""

    def __init__(self, config: BackoffConfig):
        self.config = config

    @abstractmethod
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number"""
        pass

    def add_jitter(self, delay: float) -> float:
        """Add jitter to delay"""
        if not self.config.jitter:
            return delay

        jitter_range = delay * self.config.jitter_ratio
        jitter = random.uniform(-jitter_range, jitter_range)
        return max(0, delay + jitter)

    def clamp_delay(self, delay: float) -> float:
        """Clamp delay to max_delay"""
        return min(delay, self.config.max_delay)


class ExponentialBackoffCalculator(BackoffCalculator):
    """Exponential backoff calculator"""

    def calculate_delay(self, attempt: int) -> float:
        """Calculate exponential delay"""
        delay = self.config.base_delay * (self.config.multiplier ** attempt)
        delay = self.clamp_delay(delay)
        return self.add_jitter(delay)


class LinearBackoffCalculator(BackoffCalculator):
    """Linear backoff calculator"""

    def calculate_delay(self, attempt: int) -> float:
        """Calculate linear delay"""
        delay = self.config.base_delay * (1 + attempt)
        delay = self.clamp_delay(delay)
        return self.add_jitter(delay)


class FixedBackoffCalculator(BackoffCalculator):
    """Fixed delay calculator"""

    def calculate_delay(self, attempt: int) -> float:
        """Calculate fixed delay"""
        delay = self.config.base_delay
        return self.add_jitter(delay)


class FibonacciBackoffCalculator(BackoffCalculator):
    """Fibonacci backoff calculator"""

    def __init__(self, config: BackoffConfig):
        super().__init__(config)
        self._fib_cache = {0: 1, 1: 1}

    def _fibonacci(self, n: int) -> int:
        """Calculate fibonacci number with caching"""
        if n in self._fib_cache:
            return self._fib_cache[n]

        self._fib_cache[n] = self._fibonacci(n-1) + self._fibonacci(n-2)
        return self._fib_cache[n]

    def calculate_delay(self, attempt: int) -> float:
        """Calculate fibonacci delay"""
        fib_multiplier = self._fibonacci(attempt)
        delay = self.config.base_delay * fib_multiplier
        delay = self.clamp_delay(delay)
        return self.add_jitter(delay)


class ExponentialBackoff:
    """
    Exponential backoff implementation with multiple strategies

    Features:
    - Multiple backoff strategies
    - Configurable jitter
    - Maximum delay capping
    - Detailed logging
    """

    CALCULATORS = {
        BackoffStrategy.EXPONENTIAL: ExponentialBackoffCalculator,
        BackoffStrategy.LINEAR: LinearBackoffCalculator,
        BackoffStrategy.FIXED: FixedBackoffCalculator,
        BackoffStrategy.FIBONACCI: FibonacciBackoffCalculator,
    }

    def __init__(self, config: BackoffConfig):
        self.config = config
        self.calculator = self._create_calculator()

        logger.info(
            f"Backoff initialized: {config.strategy.value} "
            f"(base={config.base_delay}s, max={config.max_delay}s, "
            f"jitter={config.jitter})"
        )

    def _create_calculator(self) -> BackoffCalculator:
        """Create appropriate calculator for strategy"""
        calculator_class = self.CALCULATORS.get(self.config.strategy)
        if not calculator_class:
            raise ValueError(f"Unknown backoff strategy: {self.config.strategy}")

        return calculator_class(self.config)

    def delays(self, max_attempts: int) -> Iterator[float]:
        """Generate delays for retry attempts"""
        for attempt in range(max_attempts):
            delay = self.calculator.calculate_delay(attempt)

            logger.debug(
                f"Backoff delay for attempt {attempt + 1}: {delay:.3f}s "
                f"(strategy={self.config.strategy.value})"
            )

            yield delay

    def wait(self, attempt: int) -> None:
        """Wait for calculated delay"""
        delay = self.calculator.calculate_delay(attempt)

        logger.info(
            f"Backing off for {delay:.3f}s (attempt {attempt + 1}, "
            f"strategy={self.config.strategy.value})"
        )

        time.sleep(delay)

    async def await_delay(self, attempt: int) -> None:
        """Async wait for calculated delay"""
        import asyncio

        delay = self.calculator.calculate_delay(attempt)

        logger.info(
            f"Async backing off for {delay:.3f}s (attempt {attempt + 1}, "
            f"strategy={self.config.strategy.value})"
        )

        await asyncio.sleep(delay)

    def get_delay(self, attempt: int) -> float:
        """Get delay for specific attempt without waiting"""
        return self.calculator.calculate_delay(attempt)

    def get_total_delay(self, max_attempts: int) -> float:
        """Calculate total delay for all attempts"""
        return sum(self.delays(max_attempts))

    def get_config(self) -> dict:
        """Get backoff configuration"""
        return {
            'strategy': self.config.strategy.value,
            'base_delay': self.config.base_delay,
            'max_delay': self.config.max_delay,
            'multiplier': self.config.multiplier,
            'jitter': self.config.jitter,
            'jitter_ratio': self.config.jitter_ratio
        }


def create_exponential_backoff(
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    multiplier: float = 2.0,
    jitter: bool = True,
    jitter_ratio: float = 0.1
) -> ExponentialBackoff:
    """Create exponential backoff with common configuration"""
    config = BackoffConfig(
        base_delay=base_delay,
        max_delay=max_delay,
        multiplier=multiplier,
        jitter=jitter,
        jitter_ratio=jitter_ratio,
        strategy=BackoffStrategy.EXPONENTIAL
    )
    return ExponentialBackoff(config)


def create_linear_backoff(
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter: bool = True,
    jitter_ratio: float = 0.1
) -> ExponentialBackoff:
    """Create linear backoff with common configuration"""
    config = BackoffConfig(
        base_delay=base_delay,
        max_delay=max_delay,
        jitter=jitter,
        jitter_ratio=jitter_ratio,
        strategy=BackoffStrategy.LINEAR
    )
    return ExponentialBackoff(config)


def create_fibonacci_backoff(
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    jitter_ratio: float = 0.1
) -> ExponentialBackoff:
    """Create fibonacci backoff with common configuration"""
    config = BackoffConfig(
        base_delay=base_delay,
        max_delay=max_delay,
        jitter=jitter,
        jitter_ratio=jitter_ratio,
        strategy=BackoffStrategy.FIBONACCI
    )
    return ExponentialBackoff(config)