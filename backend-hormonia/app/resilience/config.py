"""
Resilience Configuration Management

Centralized configuration for all resilience patterns.
"""

import os
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import logging

from .circuit_breaker.breaker import CircuitBreakerConfig
from .retry.backoff import BackoffConfig, BackoffStrategy
from .retry.retry_manager import RetryConfig
from .rate_limit.rate_limiter import RateLimitConfig, RateLimitStrategy

logger = logging.getLogger(__name__)


@dataclass
class ResilienceConfig:
    """Master configuration for all resilience patterns"""

    # Circuit Breaker Configuration
    circuit_breaker: CircuitBreakerConfig

    # Retry Configuration
    retry: RetryConfig

    # Rate Limiting Configuration
    rate_limit: RateLimitConfig

    # Health Check Configuration
    health_check_enabled: bool = True
    health_check_cache_ttl: float = 30.0

    # Metrics Configuration
    metrics_enabled: bool = True
    metrics_retention_hours: int = 24
    metrics_collection_interval: int = 60

    # Dead Letter Queue Configuration
    dead_letter_enabled: bool = True
    dead_letter_max_age_hours: int = 24
    dead_letter_max_retries: int = 3

    # Environment-specific settings
    environment: str = "development"
    debug_mode: bool = False

    @classmethod
    def create_default(cls) -> "ResilienceConfig":
        """Create default configuration"""
        return cls(
            circuit_breaker=CircuitBreakerConfig(),
            retry=RetryConfig(),
            rate_limit=RateLimitConfig(),
        )

    @classmethod
    def create_production(cls) -> "ResilienceConfig":
        """Create production-optimized configuration"""
        return cls(
            circuit_breaker=CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=120.0,
                success_threshold=3,
                timeout=30.0,
                monitor_window=300,
                min_requests=10,
            ),
            retry=RetryConfig(
                max_attempts=5,
                backoff_config=BackoffConfig(
                    base_delay=1.0,
                    max_delay=60.0,
                    multiplier=2.0,
                    jitter=True,
                    strategy=BackoffStrategy.EXPONENTIAL,
                ),
                timeout=30.0,
                enable_dead_letter=True,
            ),
            rate_limit=RateLimitConfig(
                requests_per_second=50.0,
                burst_size=200,
                strategy=RateLimitStrategy.PER_USER,
            ),
            health_check_enabled=True,
            health_check_cache_ttl=60.0,
            metrics_enabled=True,
            metrics_retention_hours=72,
            metrics_collection_interval=30,
            environment="production",
            debug_mode=False,
        )

    @classmethod
    def create_development(cls) -> "ResilienceConfig":
        """Create development-optimized configuration"""
        return cls(
            circuit_breaker=CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=30.0,
                success_threshold=2,
                timeout=10.0,
                monitor_window=60,
                min_requests=5,
            ),
            retry=RetryConfig(
                max_attempts=3,
                backoff_config=BackoffConfig(
                    base_delay=0.5,
                    max_delay=10.0,
                    multiplier=2.0,
                    jitter=True,
                    strategy=BackoffStrategy.EXPONENTIAL,
                ),
                timeout=10.0,
                enable_dead_letter=True,
            ),
            rate_limit=RateLimitConfig(
                requests_per_second=100.0,
                burst_size=500,
                strategy=RateLimitStrategy.PER_IP,
            ),
            health_check_enabled=True,
            health_check_cache_ttl=10.0,
            metrics_enabled=True,
            metrics_retention_hours=4,
            metrics_collection_interval=60,
            environment="development",
            debug_mode=True,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResilienceConfig":
        """Create configuration from dictionary"""
        # Extract circuit breaker config
        cb_data = data.get("circuit_breaker", {})
        circuit_breaker = CircuitBreakerConfig(**cb_data)

        # Extract retry config
        retry_data = data.get("retry", {})
        backoff_data = retry_data.get("backoff_config", {})

        # Handle backoff strategy enum
        if "strategy" in backoff_data and isinstance(backoff_data["strategy"], str):
            backoff_data["strategy"] = BackoffStrategy(backoff_data["strategy"])

        backoff_config = BackoffConfig(**backoff_data)
        retry_data["backoff_config"] = backoff_config

        # Handle retryable exceptions tuple
        if "retryable_exceptions" in retry_data:
            retry_data.pop("retryable_exceptions")  # Can't serialize exceptions
        if "stop_exceptions" in retry_data:
            retry_data.pop("stop_exceptions")  # Can't serialize exceptions

        retry = RetryConfig(**retry_data)

        # Extract rate limit config
        rl_data = data.get("rate_limit", {})

        # Handle strategy enum
        if "strategy" in rl_data and isinstance(rl_data["strategy"], str):
            rl_data["strategy"] = RateLimitStrategy(rl_data["strategy"])

        rate_limit = RateLimitConfig(**rl_data)

        # Create configuration
        return cls(
            circuit_breaker=circuit_breaker,
            retry=retry,
            rate_limit=rate_limit,
            health_check_enabled=data.get("health_check_enabled", True),
            health_check_cache_ttl=data.get("health_check_cache_ttl", 30.0),
            metrics_enabled=data.get("metrics_enabled", True),
            metrics_retention_hours=data.get("metrics_retention_hours", 24),
            metrics_collection_interval=data.get("metrics_collection_interval", 60),
            dead_letter_enabled=data.get("dead_letter_enabled", True),
            dead_letter_max_age_hours=data.get("dead_letter_max_age_hours", 24),
            dead_letter_max_retries=data.get("dead_letter_max_retries", 3),
            environment=data.get("environment", "development"),
            debug_mode=data.get("debug_mode", False),
        )


class ConfigManager:
    """
    Configuration manager for resilience patterns

    Features:
    - Environment-based configuration
    - File-based configuration
    - Environment variable overrides
    - Hot reload support
    - Validation
    """

    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = Path(config_dir) if config_dir else Path("config")
        self.config_dir.mkdir(exist_ok=True)

        self._current_config: Optional[ResilienceConfig] = None
        self._file_watch_enabled = False

        logger.info(f"Config manager initialized (dir: {self.config_dir})")

    def load_config(self, environment: Optional[str] = None) -> ResilienceConfig:
        """
        Load configuration for specified environment

        Priority:
        1. Environment-specific file (config/{env}.json)
        2. Default file (config/default.json)
        3. Environment variables
        4. Built-in defaults
        """
        if environment is None:
            environment = os.getenv("ENVIRONMENT", "development")

        config = None

        # Try environment-specific file
        env_file = self.config_dir / f"{environment}.json"
        if env_file.exists():
            try:
                config = self._load_from_file(env_file)
                logger.info(f"Loaded configuration from {env_file}")
            except Exception as e:
                logger.warning(f"Failed to load config from {env_file}: {e}")

        # Try default file
        if config is None:
            default_file = self.config_dir / "default.json"
            if default_file.exists():
                try:
                    config = self._load_from_file(default_file)
                    logger.info(f"Loaded configuration from {default_file}")
                except Exception as e:
                    logger.warning(f"Failed to load config from {default_file}: {e}")

        # Use built-in defaults
        if config is None:
            if environment == "production":
                config = ResilienceConfig.create_production()
            else:
                config = ResilienceConfig.create_development()

            logger.info(f"Using built-in {environment} configuration")

        # Apply environment variable overrides
        config = self._apply_env_overrides(config)

        # Validate configuration
        self._validate_config(config)

        self._current_config = config
        return config

    def _load_from_file(self, file_path: Path) -> ResilienceConfig:
        """Load configuration from JSON file"""
        with open(file_path, "r") as f:
            data = json.load(f)

        return ResilienceConfig.from_dict(data)

    def save_config(self, config: ResilienceConfig, environment: str):
        """Save configuration to file"""
        file_path = self.config_dir / f"{environment}.json"

        # Convert to dict and make JSON serializable
        config_dict = config.to_dict()
        config_dict = self._make_json_serializable(config_dict)

        with open(file_path, "w") as f:
            json.dump(config_dict, f, indent=2)

        logger.info(f"Saved configuration to {file_path}")

    def _make_json_serializable(self, obj):
        """Make object JSON serializable"""
        if isinstance(obj, dict):
            return {k: self._make_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._make_json_serializable(item) for item in obj]
        elif hasattr(obj, "value"):  # Enum
            return obj.value
        elif hasattr(obj, "__dict__"):  # Object
            return self._make_json_serializable(obj.__dict__)
        else:
            return obj

    def _apply_env_overrides(self, config: ResilienceConfig) -> ResilienceConfig:
        """Apply environment variable overrides"""
        # Circuit breaker overrides
        if os.getenv("CB_FAILURE_THRESHOLD"):
            config.circuit_breaker.failure_threshold = int(
                os.getenv("CB_FAILURE_THRESHOLD")
            )

        if os.getenv("CB_RECOVERY_TIMEOUT"):
            config.circuit_breaker.recovery_timeout = float(
                os.getenv("CB_RECOVERY_TIMEOUT")
            )

        # Retry overrides
        if os.getenv("RETRY_MAX_ATTEMPTS"):
            config.retry.max_attempts = int(os.getenv("RETRY_MAX_ATTEMPTS"))

        if os.getenv("RETRY_BASE_DELAY"):
            config.retry.backoff_config.base_delay = float(
                os.getenv("RETRY_BASE_DELAY")
            )

        # Rate limit overrides
        if os.getenv("RATE_LIMIT_RPS"):
            config.rate_limit.requests_per_second = float(os.getenv("RATE_LIMIT_RPS"))

        if os.getenv("RATE_LIMIT_BURST"):
            config.rate_limit.burst_size = int(os.getenv("RATE_LIMIT_BURST"))

        # Feature toggles
        if os.getenv("HEALTH_CHECK_ENABLED"):
            config.health_check_enabled = (
                os.getenv("HEALTH_CHECK_ENABLED").lower() == "true"
            )

        if os.getenv("METRICS_ENABLED"):
            config.metrics_enabled = os.getenv("METRICS_ENABLED").lower() == "true"

        if os.getenv("DEBUG_MODE"):
            config.debug_mode = os.getenv("DEBUG_MODE").lower() == "true"

        return config

    def _validate_config(self, config: ResilienceConfig):
        """Validate configuration values"""
        errors = []

        # Circuit breaker validation
        if config.circuit_breaker.failure_threshold <= 0:
            errors.append("Circuit breaker failure_threshold must be positive")

        if config.circuit_breaker.recovery_timeout <= 0:
            errors.append("Circuit breaker recovery_timeout must be positive")

        # Retry validation
        if config.retry.max_attempts <= 0:
            errors.append("Retry max_attempts must be positive")

        if config.retry.backoff_config.base_delay <= 0:
            errors.append("Retry base_delay must be positive")

        # Rate limit validation
        if config.rate_limit.requests_per_second <= 0:
            errors.append("Rate limit requests_per_second must be positive")

        if config.rate_limit.burst_size <= 0:
            errors.append("Rate limit burst_size must be positive")

        # Metrics validation
        if config.metrics_retention_hours <= 0:
            errors.append("Metrics retention_hours must be positive")

        if config.metrics_collection_interval <= 0:
            errors.append("Metrics collection_interval must be positive")

        if errors:
            raise ValueError("Configuration validation failed:\n" + "\n".join(errors))

        logger.info("Configuration validation passed")

    def get_current_config(self) -> Optional[ResilienceConfig]:
        """Get currently loaded configuration"""
        return self._current_config

    def create_sample_configs(self):
        """Create sample configuration files"""
        # Development config
        dev_config = ResilienceConfig.create_development()
        self.save_config(dev_config, "development")

        # Production config
        prod_config = ResilienceConfig.create_production()
        self.save_config(prod_config, "production")

        # Default config
        default_config = ResilienceConfig.create_default()
        self.save_config(default_config, "default")

        logger.info("Created sample configuration files")

    def get_config_summary(self) -> Dict[str, Any]:
        """Get configuration summary"""
        if not self._current_config:
            return {"error": "No configuration loaded"}

        config = self._current_config
        return {
            "environment": config.environment,
            "debug_mode": config.debug_mode,
            "circuit_breaker": {
                "failure_threshold": config.circuit_breaker.failure_threshold,
                "recovery_timeout": config.circuit_breaker.recovery_timeout,
                "timeout": config.circuit_breaker.timeout,
            },
            "retry": {
                "max_attempts": config.retry.max_attempts,
                "strategy": config.retry.backoff_config.strategy.value,
                "base_delay": config.retry.backoff_config.base_delay,
                "max_delay": config.retry.backoff_config.max_delay,
            },
            "rate_limit": {
                "requests_per_second": config.rate_limit.requests_per_second,
                "burst_size": config.rate_limit.burst_size,
                "strategy": config.rate_limit.strategy.value,
            },
            "features": {
                "health_checks": config.health_check_enabled,
                "metrics": config.metrics_enabled,
                "dead_letter": config.dead_letter_enabled,
            },
        }


# Global configuration manager
config_manager = ConfigManager()
