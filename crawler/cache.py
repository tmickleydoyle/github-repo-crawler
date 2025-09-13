"""
Simple caching utilities for the GitHub crawler.

Provides lightweight caching mechanisms to avoid repeated expensive operations
while maintaining memory efficiency.
"""

from typing import Any, Optional, Dict, TypeVar, Callable
from functools import wraps
import time
import hashlib
import json

T = TypeVar('T')


class SimpleCache:
    """
    A simple in-memory cache with TTL (time-to-live) support.
    
    Designed for lightweight caching of API responses and computed values
    with automatic expiration to prevent memory bloat.
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        """
        Initialize cache with size and TTL limits.
        
        Args:
            max_size: Maximum number of items to cache
            default_ttl: Default time-to-live in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._access_times: Dict[str, float] = {}
    
    def _generate_key(self, *args, **kwargs) -> str:
        """Generate a cache key from function arguments."""
        # Create a deterministic key from arguments
        key_data = {
            'args': args,
            'kwargs': sorted(kwargs.items()) if kwargs else {}
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _cleanup_expired(self):
        """Remove expired entries from cache."""
        current_time = time.time()
        expired_keys = []
        
        for key, entry in self._cache.items():
            if current_time > entry['expires_at']:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
            self._access_times.pop(key, None)
    
    def _cleanup_lru(self):
        """Remove least recently used entries if cache is full."""
        if len(self._cache) <= self.max_size:
            return
        
        # Sort by access time and remove oldest entries
        sorted_keys = sorted(self._access_times.items(), key=lambda x: x[1])
        keys_to_remove = sorted_keys[:len(self._cache) - self.max_size]
        
        for key, _ in keys_to_remove:
            self._cache.pop(key, None)
            self._access_times.pop(key, None)
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if it exists and is not expired."""
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        current_time = time.time()
        
        if current_time > entry['expires_at']:
            # Entry expired, remove it
            del self._cache[key]
            self._access_times.pop(key, None)
            return None
        
        # Update access time
        self._access_times[key] = current_time
        return entry['value']
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with optional TTL override."""
        if ttl is None:
            ttl = self.default_ttl
        
        current_time = time.time()
        
        # Clean up before adding
        self._cleanup_expired()
        self._cleanup_lru()
        
        self._cache[key] = {
            'value': value,
            'expires_at': current_time + ttl,
            'created_at': current_time
        }
        self._access_times[key] = current_time
    
    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._access_times.clear()
    
    def size(self) -> int:
        """Get current cache size."""
        return len(self._cache)
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            'size': len(self._cache),
            'max_size': self.max_size,
            'default_ttl': self.default_ttl,
        }


# Global cache instance for the crawler
_global_cache = SimpleCache(max_size=500, default_ttl=300)


def cached(ttl: int = 300, cache_instance: Optional[SimpleCache] = None):
    """
    Decorator for caching function results.
    
    Args:
        ttl: Time-to-live in seconds
        cache_instance: Optional cache instance (uses global if None)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        cache = cache_instance or _global_cache
        
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Generate cache key
            key = f"{func.__name__}:{cache._generate_key(*args, **kwargs)}"
            
            # Try to get from cache
            cached_result = cache.get(key)
            if cached_result is not None:
                return cached_result
            
            # Compute result and cache it
            result = func(*args, **kwargs)
            cache.set(key, result, ttl)
            return result
        
        return wrapper
    return decorator


def get_cache_stats() -> Dict[str, Any]:
    """Get global cache statistics."""
    return _global_cache.stats()


def clear_cache() -> None:
    """Clear global cache."""
    _global_cache.clear()