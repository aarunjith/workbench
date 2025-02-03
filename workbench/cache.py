from redis import Redis
import os
import json
from logging import getLogger

logger = getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "password")
REDIS_SSL = bool(int(os.getenv("REDIS_SSL", "0")))

REDIS = Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD)


def cache_data(key, data, **kwargs):
    status = REDIS.set(key, json.dumps(data), **kwargs)
    logger.info(f"Caching {key}")
    return status


def fetch_cache(key):
    return REDIS.get(key)


def cache(prefix, kwarg_name="exp_id", ex=300, transformer=lambda x: x):
    def decorator(func):
        def wrapper(*args, **kwargs):
            output = func(*args, **kwargs)
            exp_id = kwargs.get(kwarg_name)
            exp_id = transformer(exp_id)
            key = f"{prefix}_{exp_id}"
            status = cache_data(key, output, ex=ex)
            if not status:
                logger.warning(
                    f"Caching failed for the function call {func._name__} with args {args} and kwargs {kwargs}"
                )
            return output

        return wrapper

    return decorator


def from_cache(prefix, kwarg_name="exp_id", transformer=lambda x: x, ex=300):
    def decorator(func):
        def wrapper(*args, **kwargs):
            exp_id = kwargs.get(kwarg_name)
            exp_id = transformer(exp_id)
            key = f"{prefix}_{exp_id}"
            logger.info(f"Transformed key: {key}")
            data = fetch_cache(key)
            if data:
                output = json.loads(data)
            else:
                logger.info(
                    f"Cache not found for the function call {func.__name__} with args {args} and kwargs {kwargs}"
                )
                output = func(*args, **kwargs)
                status = cache_data(key, output, ex=ex)
                if not status:
                    logger.warning(
                        f"Caching failed for the function call {func.__name__} with args {args} and kwargs {kwargs}"
                    )
            return output

        return wrapper

    return decorator
