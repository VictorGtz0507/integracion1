import os
import threading
import time
from collections import defaultdict
import redis

_client = None
_client_url = None
_metrics = defaultdict(lambda: {"count": 0, "errors": 0, "total_ms": 0.0})
_metrics_lock = threading.Lock()


class RedisUnavailable(RuntimeError):
    pass


def get_redis():
    global _client, _client_url
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        raise RedisUnavailable("REDIS_URL must be configured")
    if _client is None or _client_url != redis_url:
        _client = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=float(os.getenv("REDIS_CONNECT_TIMEOUT", "2")),
            socket_timeout=float(os.getenv("REDIS_SOCKET_TIMEOUT", "2")),
            health_check_interval=30,
        )
        _client_url = redis_url
    return _client


def require_redis():
    client = get_redis()
    started = time.perf_counter()
    try:
        client.ping()
        record_metric("redis.ping", started)
        return client
    except redis.RedisError as exc:
        record_metric("redis.ping", started, failed=True)
        raise RedisUnavailable("Redis is required for this operation") from exc


def record_metric(name, started=None, failed=False):
    elapsed_ms = (time.perf_counter() - started) * 1000 if started is not None else 0
    with _metrics_lock:
        metric = _metrics[name]
        metric["count"] += 1
        metric["errors"] += int(failed)
        metric["total_ms"] += elapsed_ms


def timed_redis_call(name, operation, *args, **kwargs):
    started = time.perf_counter()
    try:
        result = operation(*args, **kwargs)
        record_metric(name, started)
        return result
    except (redis.RedisError, RedisUnavailable):
        record_metric(name, started, failed=True)
        raise


def metrics_snapshot():
    with _metrics_lock:
        snapshot = {
            name: {
                "count": metric["count"],
                "errors": metric["errors"],
                "average_ms": round(metric["total_ms"] / metric["count"], 3)
                if metric["count"]
                else 0,
            }
            for name, metric in _metrics.items()
        }
    try:
        client = get_redis()
        client.ping()
        memory = client.info("memory")
        snapshot["redis"] = {
            "connected": True,
            "used_memory_bytes": int(memory.get("used_memory", 0)),
            "maxmemory_bytes": int(memory.get("maxmemory", 0)),
        }
    except (redis.RedisError, RedisUnavailable):
        snapshot["redis"] = {"connected": False}
    return snapshot


def acquire_task_lock(name, ttl_seconds):
    client = require_redis()
    lock_name = "task:lock:" + name
    started = time.perf_counter()
    try:
        acquired = bool(client.set(lock_name, "1", nx=True, ex=max(1, int(ttl_seconds))))
        record_metric("redis.task_lock", started)
        return acquired
    except redis.RedisError as exc:
        record_metric("redis.task_lock", started, failed=True)
        raise RedisUnavailable("Redis is required for task coordination") from exc


def invalidate_book_catalog_cache():
    started = time.perf_counter()
    try:
        client = get_redis()
        keys = list(client.scan_iter(match="books:*", count=100))
        if keys:
            client.delete(*keys)
        record_metric("books.cache_invalidation", started)
        return True
    except (redis.RedisError, RedisUnavailable):
        record_metric("books.cache_error", started, failed=True)
        return False
