"""
Token Bucket Algorithm Implementation

Production-ready token bucket for rate limiting.
"""

import time
import threading
from typing import Dict, Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TokenBucketConfig:
    """Token bucket configuration"""
    capacity: int = 100               # Maximum tokens in bucket
    refill_rate: float = 10.0         # Tokens per second refill rate
    initial_tokens: Optional[int] = None  # Initial tokens (defaults to capacity)

    def __post_init__(self):
        if self.initial_tokens is None:
            self.initial_tokens = self.capacity


class TokenBucket:
    """
    Token bucket implementation for rate limiting

    Features:
    - Thread-safe token management
    - Configurable capacity and refill rate
    - Precise timing for token refill
    - Metrics collection
    """

    def __init__(self, config: TokenBucketConfig, name: str = "default"):
        self.config = config
        self.name = name

        # Token state
        self._tokens = float(config.initial_tokens)
        self._last_refill = time.time()
        self._lock = threading.Lock()

        # Metrics
        self._total_requests = 0
        self._allowed_requests = 0
        self._denied_requests = 0
        self._tokens_consumed = 0

        logger.info(
            f"Token bucket '{name}' initialized "
            f"(capacity={config.capacity}, rate={config.refill_rate}/s)"
        )

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from bucket

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if not enough tokens
        """
        with self._lock:
            self._refill_tokens()
            self._total_requests += 1

            if self._tokens >= tokens:
                self._tokens -= tokens
                self._allowed_requests += 1
                self._tokens_consumed += tokens

                logger.debug(
                    f"Token bucket '{self.name}' consumed {tokens} tokens "
                    f"(remaining: {self._tokens:.1f})"
                )
                return True
            else:
                self._denied_requests += 1

                logger.debug(
                    f"Token bucket '{self.name}' denied request for {tokens} tokens "
                    f"(available: {self._tokens:.1f})"
                )
                return False

    def peek(self) -> float:
        """
        Get current token count without consuming

        Returns:
            Current number of tokens in bucket
        """
        with self._lock:
            self._refill_tokens()
            return self._tokens

    def time_until_tokens(self, tokens: int = 1) -> float:
        """
        Calculate time until specified tokens are available

        Args:
            tokens: Number of tokens needed

        Returns:
            Time in seconds until tokens are available (0 if already available)
        """
        with self._lock:
            self._refill_tokens()

            if self._tokens >= tokens:
                return 0.0

            tokens_needed = tokens - self._tokens
            time_needed = tokens_needed / self.config.refill_rate

            return time_needed

    def _refill_tokens(self):
        """Refill tokens based on elapsed time"""
        current_time = time.time()
        elapsed = current_time - self._last_refill

        if elapsed > 0:
            # Calculate tokens to add
            tokens_to_add = elapsed * self.config.refill_rate

            # Add tokens up to capacity
            self._tokens = min(self.config.capacity, self._tokens + tokens_to_add)
            self._last_refill = current_time

    def reset(self):
        """Reset bucket to initial state"""
        with self._lock:
            self._tokens = float(self.config.initial_tokens)
            self._last_refill = time.time()

            logger.info(f"Token bucket '{self.name}' reset")

    def get_metrics(self) -> Dict[str, Any]:
        """Get bucket metrics"""
        with self._lock:
            self._refill_tokens()

            success_rate = (
                self._allowed_requests / max(1, self._total_requests)
            )

            return {
                'name': self.name,
                'current_tokens': self._tokens,
                'capacity': self.config.capacity,
                'refill_rate': self.config.refill_rate,
                'total_requests': self._total_requests,
                'allowed_requests': self._allowed_requests,
                'denied_requests': self._denied_requests,
                'success_rate': success_rate,
                'tokens_consumed': self._tokens_consumed,
                'utilization': 1.0 - (self._tokens / self.config.capacity)
            }

    def get_status(self) -> Dict[str, Any]:
        """Get current bucket status"""
        with self._lock:
            self._refill_tokens()

            return {
                'tokens': self._tokens,
                'capacity': self.config.capacity,
                'utilization_percent': (1.0 - (self._tokens / self.config.capacity)) * 100,
                'is_full': self._tokens >= self.config.capacity,
                'is_empty': self._tokens == 0
            }


class TokenBucketManager:
    """
    Manager for multiple token buckets

    Features:
    - Named bucket management
    - Automatic bucket creation
    - Cleanup of unused buckets
    - Aggregated metrics
    """

    def __init__(self, default_config: Optional[TokenBucketConfig] = None):
        self.default_config = default_config or TokenBucketConfig()
        self._buckets: Dict[str, TokenBucket] = {}
        self._lock = threading.Lock()

        # Cleanup tracking
        self._last_access: Dict[str, float] = {}
        self._cleanup_interval = 3600.0  # 1 hour
        self._last_cleanup = time.time()

        logger.info("Token bucket manager initialized")

    def get_bucket(self,
                   bucket_id: str,
                   config: Optional[TokenBucketConfig] = None) -> TokenBucket:
        """
        Get or create token bucket

        Args:
            bucket_id: Unique bucket identifier
            config: Optional bucket configuration (uses default if None)

        Returns:
            TokenBucket instance
        """
        with self._lock:
            # Check if bucket exists
            if bucket_id in self._buckets:
                self._last_access[bucket_id] = time.time()
                return self._buckets[bucket_id]

            # Create new bucket
            bucket_config = config or self.default_config
            bucket = TokenBucket(bucket_config, name=bucket_id)

            self._buckets[bucket_id] = bucket
            self._last_access[bucket_id] = time.time()

            logger.info(f"Created new token bucket: {bucket_id}")
            return bucket

    def consume(self,
                bucket_id: str,
                tokens: int = 1,
                config: Optional[TokenBucketConfig] = None) -> bool:
        """
        Consume tokens from specified bucket

        Args:
            bucket_id: Bucket identifier
            tokens: Number of tokens to consume
            config: Optional bucket configuration for new buckets

        Returns:
            True if tokens were consumed, False otherwise
        """
        bucket = self.get_bucket(bucket_id, config)
        return bucket.consume(tokens)

    def peek(self,
             bucket_id: str,
             config: Optional[TokenBucketConfig] = None) -> float:
        """
        Get current token count for bucket

        Args:
            bucket_id: Bucket identifier
            config: Optional bucket configuration for new buckets

        Returns:
            Current number of tokens
        """
        bucket = self.get_bucket(bucket_id, config)
        return bucket.peek()

    def time_until_tokens(self,
                         bucket_id: str,
                         tokens: int = 1,
                         config: Optional[TokenBucketConfig] = None) -> float:
        """
        Calculate time until tokens are available in bucket

        Args:
            bucket_id: Bucket identifier
            tokens: Number of tokens needed
            config: Optional bucket configuration for new buckets

        Returns:
            Time in seconds until tokens are available
        """
        bucket = self.get_bucket(bucket_id, config)
        return bucket.time_until_tokens(tokens)

    def remove_bucket(self, bucket_id: str) -> bool:
        """
        Remove bucket from manager

        Args:
            bucket_id: Bucket identifier

        Returns:
            True if bucket was removed, False if not found
        """
        with self._lock:
            if bucket_id in self._buckets:
                del self._buckets[bucket_id]
                del self._last_access[bucket_id]
                logger.info(f"Removed token bucket: {bucket_id}")
                return True
            return False

    def cleanup_unused_buckets(self, max_age: float = 3600.0):
        """
        Remove buckets that haven't been used recently

        Args:
            max_age: Maximum age in seconds for unused buckets
        """
        current_time = time.time()

        with self._lock:
            expired_buckets = []

            for bucket_id, last_access in self._last_access.items():
                if current_time - last_access > max_age:
                    expired_buckets.append(bucket_id)

            for bucket_id in expired_buckets:
                del self._buckets[bucket_id]
                del self._last_access[bucket_id]

            self._last_cleanup = current_time

            if expired_buckets:
                logger.info(f"Cleaned up {len(expired_buckets)} unused token buckets")

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get metrics for all buckets"""
        with self._lock:
            # Cleanup if needed
            current_time = time.time()
            if current_time - self._last_cleanup > self._cleanup_interval:
                self.cleanup_unused_buckets()

            bucket_metrics = {}
            total_requests = 0
            total_allowed = 0
            total_denied = 0

            for bucket_id, bucket in self._buckets.items():
                metrics = bucket.get_metrics()
                bucket_metrics[bucket_id] = metrics

                total_requests += metrics['total_requests']
                total_allowed += metrics['allowed_requests']
                total_denied += metrics['denied_requests']

            overall_success_rate = (
                total_allowed / max(1, total_requests)
            )

            return {
                'total_buckets': len(self._buckets),
                'total_requests': total_requests,
                'total_allowed': total_allowed,
                'total_denied': total_denied,
                'overall_success_rate': overall_success_rate,
                'buckets': bucket_metrics
            }

    def get_bucket_names(self) -> list:
        """Get list of bucket names"""
        with self._lock:
            return list(self._buckets.keys())


# Global token bucket manager
token_bucket_manager = TokenBucketManager()