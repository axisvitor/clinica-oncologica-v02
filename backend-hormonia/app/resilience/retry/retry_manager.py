"""
Retry Manager Implementation

Comprehensive retry management with dead letter queue and metrics.
"""

import time
import asyncio
from typing import Any, Callable, Optional, List, Dict, Type, Union
from dataclasses import dataclass, field
from enum import Enum
import logging

from .backoff import ExponentialBackoff, BackoffConfig, create_exponential_backoff
from .dead_letter import DeadLetterQueue

logger = logging.getLogger(__name__)


class RetryResult(Enum):
    """Retry operation results"""
    SUCCESS = "success"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


@dataclass
class RetryConfig:
    """Retry configuration"""
    max_attempts: int = 3                    # Maximum retry attempts
    backoff_config: BackoffConfig = field(default_factory=BackoffConfig)
    retryable_exceptions: tuple = (Exception,)  # Exceptions to retry
    stop_exceptions: tuple = ()              # Exceptions to never retry
    timeout: Optional[float] = None          # Operation timeout
    enable_dead_letter: bool = True          # Enable dead letter queue

    # Conditional retry
    retry_condition: Optional[Callable] = None  # Custom retry condition

    # Logging
    log_attempts: bool = True
    log_level: int = logging.INFO


@dataclass
class RetryAttempt:
    """Information about a retry attempt"""
    attempt_number: int
    start_time: float
    end_time: Optional[float] = None
    exception: Optional[Exception] = None
    result: Optional[Any] = None
    delay: Optional[float] = None

    @property
    def duration(self) -> Optional[float]:
        """Get attempt duration"""
        if self.end_time and self.start_time:
            return self.end_time - self.start_time
        return None

    @property
    def success(self) -> bool:
        """Check if attempt was successful"""
        return self.exception is None


@dataclass
class RetryExecution:
    """Complete retry execution information"""
    function_name: str
    start_time: float
    end_time: Optional[float] = None
    attempts: List[RetryAttempt] = field(default_factory=list)
    final_result: Optional[Any] = None
    final_exception: Optional[Exception] = None
    result: RetryResult = RetryResult.FAILED

    @property
    def total_duration(self) -> Optional[float]:
        """Get total execution duration"""
        if self.end_time and self.start_time:
            return self.end_time - self.start_time
        return None

    @property
    def total_attempts(self) -> int:
        """Get total number of attempts"""
        return len(self.attempts)

    @property
    def success(self) -> bool:
        """Check if execution was successful"""
        return self.result == RetryResult.SUCCESS


class RetryManager:
    """
    Comprehensive retry manager

    Features:
    - Configurable retry strategies
    - Dead letter queue for persistent failures
    - Detailed metrics and logging
    - Conditional retry logic
    - Timeout support
    """

    def __init__(self,
                 config: RetryConfig,
                 name: str = "default",
                 dead_letter_queue: Optional[DeadLetterQueue] = None):
        self.config = config
        self.name = name
        self.backoff = ExponentialBackoff(config.backoff_config)

        # Dead letter queue
        if config.enable_dead_letter:
            self.dead_letter_queue = dead_letter_queue or DeadLetterQueue()
        else:
            self.dead_letter_queue = None

        # Metrics
        self._executions: List[RetryExecution] = []
        self._total_attempts = 0
        self._successful_executions = 0
        self._failed_executions = 0
        self._dead_letter_count = 0

        logger.info(f"Retry manager '{name}' initialized with {config.max_attempts} max attempts")

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry logic"""
        execution = RetryExecution(
            function_name=getattr(func, '__name__', str(func)),
            start_time=time.time()
        )

        for attempt_num in range(self.config.max_attempts):
            attempt = RetryAttempt(
                attempt_number=attempt_num + 1,
                start_time=time.time()
            )

            try:
                # Execute with timeout if configured
                if self.config.timeout:
                    result = self._execute_with_timeout(func, *args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                # Success!
                attempt.end_time = time.time()
                attempt.result = result
                execution.attempts.append(attempt)
                execution.final_result = result
                execution.result = RetryResult.SUCCESS
                execution.end_time = time.time()

                self._record_success(execution)

                if self.config.log_attempts:
                    logger.log(
                        self.config.log_level,
                        f"Retry manager '{self.name}' succeeded on attempt {attempt_num + 1}"
                    )

                return result

            except Exception as e:
                attempt.end_time = time.time()
                attempt.exception = e
                execution.attempts.append(attempt)

                # Check if we should retry this exception
                if not self._should_retry(e, attempt_num):
                    execution.final_exception = e
                    execution.result = RetryResult.FAILED
                    execution.end_time = time.time()

                    self._record_failure(execution, stop_retry=True)
                    raise e

                # Last attempt?
                if attempt_num == self.config.max_attempts - 1:
                    execution.final_exception = e
                    execution.result = RetryResult.FAILED
                    execution.end_time = time.time()

                    # Send to dead letter queue
                    if self.dead_letter_queue:
                        self._send_to_dead_letter(func, args, kwargs, execution)
                        execution.result = RetryResult.DEAD_LETTER

                    self._record_failure(execution)
                    raise e

                # Calculate delay for next attempt
                delay = self.backoff.get_delay(attempt_num)
                attempt.delay = delay

                if self.config.log_attempts:
                    logger.log(
                        self.config.log_level,
                        f"Retry manager '{self.name}' attempt {attempt_num + 1} failed: "
                        f"{type(e).__name__}: {str(e)}. Retrying in {delay:.3f}s"
                    )

                # Wait before retry
                self.backoff.wait(attempt_num)

        # Should never reach here, but just in case
        raise RuntimeError("Retry logic error")

    async def aexecute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute async function with retry logic"""
        execution = RetryExecution(
            function_name=getattr(func, '__name__', str(func)),
            start_time=time.time()
        )

        for attempt_num in range(self.config.max_attempts):
            attempt = RetryAttempt(
                attempt_number=attempt_num + 1,
                start_time=time.time()
            )

            try:
                # Execute with timeout if configured
                if self.config.timeout:
                    result = await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=self.config.timeout
                    )
                else:
                    result = await func(*args, **kwargs)

                # Success!
                attempt.end_time = time.time()
                attempt.result = result
                execution.attempts.append(attempt)
                execution.final_result = result
                execution.result = RetryResult.SUCCESS
                execution.end_time = time.time()

                self._record_success(execution)

                if self.config.log_attempts:
                    logger.log(
                        self.config.log_level,
                        f"Async retry manager '{self.name}' succeeded on attempt {attempt_num + 1}"
                    )

                return result

            except Exception as e:
                attempt.end_time = time.time()
                attempt.exception = e
                execution.attempts.append(attempt)

                # Check if we should retry this exception
                if not self._should_retry(e, attempt_num):
                    execution.final_exception = e
                    execution.result = RetryResult.FAILED
                    execution.end_time = time.time()

                    self._record_failure(execution, stop_retry=True)
                    raise e

                # Last attempt?
                if attempt_num == self.config.max_attempts - 1:
                    execution.final_exception = e
                    execution.result = RetryResult.FAILED
                    execution.end_time = time.time()

                    # Send to dead letter queue
                    if self.dead_letter_queue:
                        self._send_to_dead_letter(func, args, kwargs, execution)
                        execution.result = RetryResult.DEAD_LETTER

                    self._record_failure(execution)
                    raise e

                # Calculate delay for next attempt
                delay = self.backoff.get_delay(attempt_num)
                attempt.delay = delay

                if self.config.log_attempts:
                    logger.log(
                        self.config.log_level,
                        f"Async retry manager '{self.name}' attempt {attempt_num + 1} failed: "
                        f"{type(e).__name__}: {str(e)}. Retrying in {delay:.3f}s"
                    )

                # Wait before retry
                await self.backoff.await_delay(attempt_num)

        # Should never reach here, but just in case
        raise RuntimeError("Async retry logic error")

    def _execute_with_timeout(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with timeout (sync version)"""
        import signal

        def timeout_handler(signum, frame):
            raise TimeoutError(f"Function execution timed out after {self.config.timeout}s")

        # Set timeout alarm
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(int(self.config.timeout))

        try:
            result = func(*args, **kwargs)
            signal.alarm(0)  # Cancel alarm
            return result
        except Exception:
            signal.alarm(0)  # Cancel alarm
            raise

    def _should_retry(self, exception: Exception, attempt_num: int) -> bool:
        """Determine if exception should trigger a retry"""
        # Check stop exceptions first
        if isinstance(exception, self.config.stop_exceptions):
            return False

        # Check retryable exceptions
        if not isinstance(exception, self.config.retryable_exceptions):
            return False

        # Check custom retry condition
        if self.config.retry_condition:
            return self.config.retry_condition(exception, attempt_num)

        return True

    def _send_to_dead_letter(self, func: Callable, args: tuple, kwargs: dict, execution: RetryExecution):
        """Send failed execution to dead letter queue"""
        if not self.dead_letter_queue:
            return

        self.dead_letter_queue.add_message({
            'function_name': execution.function_name,
            'args': args,
            'kwargs': kwargs,
            'execution_info': {
                'total_attempts': execution.total_attempts,
                'total_duration': execution.total_duration,
                'final_exception': str(execution.final_exception),
                'attempts': [
                    {
                        'attempt_number': attempt.attempt_number,
                        'duration': attempt.duration,
                        'exception': str(attempt.exception) if attempt.exception else None
                    }
                    for attempt in execution.attempts
                ]
            },
            'retry_manager': self.name,
            'timestamp': execution.start_time
        })

        self._dead_letter_count += 1

        logger.warning(
            f"Sent failed execution to dead letter queue: "
            f"{execution.function_name} (attempts={execution.total_attempts})"
        )

    def _record_success(self, execution: RetryExecution):
        """Record successful execution"""
        self._executions.append(execution)
        self._total_attempts += execution.total_attempts
        self._successful_executions += 1

    def _record_failure(self, execution: RetryExecution, stop_retry: bool = False):
        """Record failed execution"""
        self._executions.append(execution)
        self._total_attempts += execution.total_attempts
        self._failed_executions += 1

        if stop_retry:
            logger.warning(
                f"Retry manager '{self.name}' stopped retrying due to stop condition: "
                f"{type(execution.final_exception).__name__}"
            )

    def get_metrics(self) -> Dict:
        """Get comprehensive retry metrics"""
        total_executions = self._successful_executions + self._failed_executions
        success_rate = (
            self._successful_executions / total_executions
            if total_executions > 0 else 0.0
        )

        avg_attempts = (
            self._total_attempts / total_executions
            if total_executions > 0 else 0.0
        )

        return {
            'name': self.name,
            'total_executions': total_executions,
            'successful_executions': self._successful_executions,
            'failed_executions': self._failed_executions,
            'success_rate': success_rate,
            'total_attempts': self._total_attempts,
            'average_attempts': avg_attempts,
            'dead_letter_count': self._dead_letter_count,
            'config': {
                'max_attempts': self.config.max_attempts,
                'timeout': self.config.timeout,
                'backoff_strategy': self.config.backoff_config.strategy.value
            },
            'dead_letter_queue': (
                self.dead_letter_queue.get_metrics()
                if self.dead_letter_queue else None
            )
        }

    def reset_metrics(self):
        """Reset all metrics"""
        self._executions.clear()
        self._total_attempts = 0
        self._successful_executions = 0
        self._failed_executions = 0
        self._dead_letter_count = 0

        if self.dead_letter_queue:
            self.dead_letter_queue.clear()

        logger.info(f"Retry manager '{self.name}' metrics reset")