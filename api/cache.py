import redis
import json
import hashlib
from functools import wraps
from typing import Optional, Callable
import os
import logging

logger = logging.getLogger(__name__)

# Connection pool (reuse connections)
# We use lazy connection so it doesn't crash if Redis is down
redis_pool = redis.ConnectionPool(
    host=os.getenv('REDIS_HOST', 'redis'),
    port=6379,
    db=0,
    password=os.getenv('REDIS_PASSWORD', 'secure_redis_password'),
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2
)

redis_client = redis.Redis(connection_pool=redis_pool)

def cache_key(*args, **kwargs) -> str:
    """Generate a consistent cache key from function arguments"""
    # We sort kwargs to ensure 'a=1,b=2' and 'b=2,a=1' produce the same key
    key_data = str(args) + str(sorted(kwargs.items()))
    return hashlib.md5(key_data.encode()).hexdigest()

def cached(expire: int = 3600, key_prefix: str = ""):
    """
    PERFORMANCE: Cache Decorator
    Wraps any function to store its result in Redis RAM.
    If called again with same args, returns instant result from RAM.
    
    :param expire: Time-to-Live in seconds (default 1 hour)
    :param key_prefix: Unique namespace for this cache (e.g. 'metadata')
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 1. Generate unique key
            key = f"{key_prefix}:{cache_key(*args, **kwargs)}"
            
            # 2. Try to read from RAM (Fast Path)
            try:
                cached_value = redis_client.get(key)
                if cached_value:
                    return json.loads(cached_value)
            except Exception as e:
                # If Redis fails, log it but don't crash. Fallback to DB.
                logger.warning(f"Cache read failed: {e}")
            
            # 3. Execute real function (Slow Path)
            result = func(*args, **kwargs)
            
            # 4. Store result in RAM for next time
            try:
                redis_client.setex(
                    key, 
                    expire, 
                    json.dumps(result)
                )
            except Exception as e:
                logger.warning(f"Cache write failed: {e}")
            
            return result
        return wrapper
    return decorator
