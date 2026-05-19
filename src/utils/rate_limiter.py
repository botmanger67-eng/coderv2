"""
Rate limiter implementation for controlling API request rates.

This module provides a thread-safe rate limiter that can be used to
limit the number of requests within a specified time window.
"""

import time
import threading
from typing import Dict, Optional, Tuple
from collections import deque
from dataclasses import dataclass
from enum import Enum


class RateLimitExceededError(Exception):
    """Exception raised when rate limit is exceeded."""
    pass


class RateLimitStrategy(Enum):
    """Enumeration of supported rate limiting strategies."""
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiter."""
    max_requests: int
    window_size_seconds: float
    strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW
    burst_size: Optional[int] = None


class TokenBucket:
    """Token bucket algorithm implementation."""
    
    def __init__(self, capacity: int, refill_rate: float, refill_time: float = 1.0):
        """
        Initialize token bucket.
        
        Args:
            capacity: Maximum number of tokens in bucket
            refill_rate: Number of tokens to add per refill_time
            refill_time: Time interval for refill in seconds
        """
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        if refill_rate <= 0:
            raise ValueError("Refill rate must be positive")
        if refill_time <= 0:
            raise ValueError("Refill time must be positive")
            
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.refill_time = refill_time
        self.tokens = float(capacity)
        self.last_refill_time = time.monotonic()
        self.lock = threading.Lock()
    
    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from bucket.
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            True if tokens were consumed, False otherwise
        """
        if tokens <= 0:
            raise ValueError("Tokens to consume must be positive")
            
        with self.lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill_time
        if elapsed >= self.refill_time:
            tokens_to_add = (elapsed / self.refill_time) * self.refill_rate
            self.tokens = min(self.capacity, self.tokens + tokens_to_add)
            self.last_refill_time = now


class RateLimiter:
    """
    Thread-safe rate limiter supporting multiple strategies.
    
    Supports fixed window, sliding window, and token bucket algorithms.
    """
    
    def __init__(self, config: RateLimitConfig):
        """
        Initialize rate limiter with configuration.
        
        Args:
            config: Rate limit configuration
            
        Raises:
            ValueError: If configuration is invalid
        """
        self._validate_config(config)
        self.config = config
        self.lock = threading.RLock()
        
        if config.strategy == RateLimitStrategy.TOKEN_BUCKET:
            burst = config.burst_size or config.max_requests
            refill_rate = config.max_requests / config.window_size_seconds
            self._bucket = TokenBucket(burst, refill_rate, 1.0)
        else:
            self._timestamps: Dict[str, deque] = {}
    
    def _validate_config(self, config: RateLimitConfig) -> None:
        """Validate rate limit configuration."""
        if config.max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if config.window_size_seconds <= 0:
            raise ValueError("window_size_seconds must be positive")
        if config.burst_size is not None and config.burst_size <= 0:
            raise ValueError("burst_size must be positive")
    
    def acquire(self, key: str = "default", tokens: int = 1) -> bool:
        """
        Try to acquire permission to make a request.
        
        Args:
            key: Identifier for the rate limit bucket
            tokens: Number of tokens to consume (for token bucket strategy)
            
        Returns:
            True if request is allowed, False otherwise
        """
        if not key:
            raise ValueError("Key cannot be empty")
        if tokens <= 0:
            raise ValueError("Tokens must be positive")
        
        with self.lock:
            if self.config.strategy == RateLimitStrategy.TOKEN_BUCKET:
                return self._bucket.consume(tokens)
            elif self.config.strategy == RateLimitStrategy.FIXED_WINDOW:
                return self._check_fixed_window(key)
            else:
                return self._check_sliding_window(key)
    
    def acquire_or_raise(self, key: str = "default", tokens: int = 1) -> None:
        """
        Try to acquire permission or raise exception.
        
        Args:
            key: Identifier for the rate limit bucket
            tokens: Number of tokens to consume
            
        Raises:
            RateLimitExceededError: If rate limit is exceeded
        """
        if not self.acquire(key, tokens):
            raise RateLimitExceededError(
                f"Rate limit exceeded for key '{key}'"
            )
    
    def _check_fixed_window(self, key: str) -> bool:
        """
        Check rate limit using fixed window algorithm.
        
        Args:
            key: Identifier for the rate limit bucket
            
        Returns:
            True if request is allowed
        """
        now = time.time()
        window_start = now - (now % self.config.window_size_seconds)
        
        if key not in self._timestamps:
            self._timestamps[key] = deque()
        
        timestamps = self._timestamps[key]
        
        # Remove timestamps from previous windows
        while timestamps and timestamps[0] < window_start:
            timestamps.popleft()
        
        if len(timestamps) >= self.config.max_requests:
            return False
        
        timestamps.append(now)
        return True
    
    def _check_sliding_window(self, key: str) -> bool:
        """
        Check rate limit using sliding window algorithm.
        
        Args:
            key: Identifier for the rate limit bucket
            
        Returns:
            True if request is allowed
        """
        now = time.time()
        window_start = now - self.config.window_size_seconds
        
        if key not in self._timestamps:
            self._timestamps[key] = deque()
        
        timestamps = self._timestamps[key]
        
        # Remove expired timestamps
        while timestamps and timestamps[0] < window_start:
            timestamps.popleft()
        
        if len(timestamps) >= self.config.max_requests:
            return False
        
        timestamps.append(now)
        return True
    
    def get_remaining(self, key: str = "default") -> int:
        """
        Get remaining requests allowed for the current window.
        
        Args:
            key: Identifier for the rate limit bucket
            
        Returns:
            Number of remaining requests
        """
        with self.lock:
            if self.config.strategy == RateLimitStrategy.TOKEN_BUCKET:
                return int(self._bucket.tokens)
            
            if key not in self._timestamps:
                return self.config.max_requests
            
            now = time.time()
            if self.config.strategy == RateLimitStrategy.FIXED_WINDOW:
                window_start = now - (now % self.config.window_size_seconds)
            else:
                window_start = now - self.config.window_size_seconds
            
            timestamps = self._timestamps[key]
            while timestamps and timestamps[0] < window_start:
                timestamps.popleft()
            
            return max(0, self.config.max_requests - len(timestamps))
    
    def reset(self, key: Optional[str] = None) -> None:
        """
        Reset rate limiter state.
        
        Args:
            key: Specific key to reset, or None to reset all
        """
        with self.lock:
            if key:
                self._timestamps.pop(key, None)
            else:
                self._timestamps.clear()
                if self.config.strategy == RateLimitStrategy.TOKEN_BUCKET:
                    self._bucket = TokenBucket(
                        self.config.burst_size or self.config.max_requests,
                        self.config.max_requests / self.config.window_size_seconds,
                        1.0
                    )
    
    def get_window_reset_time(self, key: str = "default") -> float:
        """
        Get time until window resets.
        
        Args:
            key: Identifier for the rate limit bucket
            
        Returns:
            Seconds until window reset
        """
        with self.lock:
            if self.config.strategy == RateLimitStrategy.TOKEN_BUCKET:
                return 0.0
            
            now = time.time()
            if self.config.strategy == RateLimitStrategy.FIXED_WINDOW:
                window_end = now - (now % self.config.window_size_seconds) + self.config.window_size_seconds
            else:
                if key in self._timestamps and self._timestamps[key]:
                    window_end = self._timestamps[key][0] + self.config.window_size_seconds
                else:
                    return 0.0
            
            return max(0.0, window_end - now)


class RateLimiterFactory:
    """Factory for creating rate limiters with common configurations."""
    
    @staticmethod
    def create_per_second(max_requests: int, burst_size: Optional[int] = None) -> RateLimiter:
        """
        Create rate limiter with per-second window.
        
        Args:
            max_requests: Maximum requests per second
            burst_size: Optional burst size for token bucket
            
        Returns:
            Configured RateLimiter instance
        """
        return RateLimiter(RateLimitConfig(
            max_requests=max_requests,
            window_size_seconds=1.0,
            burst_size=burst_size
        ))
    
    @staticmethod
    def create_per_minute(max_requests: int, burst_size: Optional[int] = None) -> RateLimiter:
        """
        Create rate limiter with per-minute window.
        
        Args:
            max_requests: Maximum requests per minute
            burst_size: Optional burst size for token bucket
            
        Returns:
            Configured RateLimiter instance
        """
        return RateLimiter(RateLimitConfig(
            max_requests=max_requests,
            window_size_seconds=60.0,
            burst_size=burst_size
        ))
    
    @staticmethod
    def create_per_hour(max_requests: int, burst_size: Optional[int] = None) -> RateLimiter:
        """
        Create rate limiter with per-hour window.
        
        Args:
            max_requests: Maximum requests per hour
            burst_size: Optional burst size for token bucket
            
        Returns:
            Configured RateLimiter instance
        """
        return RateLimiter(RateLimitConfig(
            max_requests=max_requests,
            window_size_seconds=3600.0,
            burst_size=burst_size
        ))
    
    @staticmethod
    def create_token_bucket(capacity: int, refill_rate: float, refill_time: float = 1.0) -> RateLimiter:
        """
        Create token bucket rate limiter.
        
        Args:
            capacity: Maximum token bucket capacity
            refill_rate: Tokens to add per refill_time
            refill_time: Time interval for refill
            
        Returns:
            Configured RateLimiter instance
        """
        return RateLimiter(RateLimitConfig(
            max_requests=capacity,
            window_size_seconds=refill_time * (capacity / refill_rate) if refill_rate > 0 else 1.0,
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            burst_size=capacity
        ))