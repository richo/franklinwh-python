"""Cache a function result for a specified time.

This design provides a locked cache PER DECORATOR INSTANCE so SHOULD apply
only to functions that are definitely called periodically, otherwise it may
cache arguments and results indefinitely, think 'self' for member functions.
"""

import asyncio
from datetime import datetime, timedelta
from functools import wraps


def time_cached(ttl: timedelta = timedelta(seconds=2)):
    """Decorator to cache function results for a specified time-to-live (TTL)."""

    def wrapper(func):
        __cache = {}
        __lock = asyncio.Lock()

        @wraps(func)
        async def wrapped(*args, **kwargs):
            async with __lock:
                now = datetime.now()
                for key, value in __cache.copy().items():
                    if now > value[0]:
                        del __cache[key]
                key = (args, frozenset(kwargs.items()))
                if key not in __cache:
                    __cache[key] = (now + ttl, await func(*args, **kwargs))
                return __cache[key][1]

        setattr(wrapped, "clear", __cache.clear)
        return wrapped

    return wrapper
