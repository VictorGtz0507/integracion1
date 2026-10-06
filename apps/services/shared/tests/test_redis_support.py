import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import redis

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared import redis_support


class RedisSupportTests(unittest.TestCase):
    def test_task_lock_is_set_once_with_expiry(self):
        client = Mock()
        client.set.return_value = True
        with patch.object(redis_support, "require_redis", return_value=client):
            self.assertTrue(redis_support.acquire_task_lock("catalog-sync", 30))
        client.set.assert_called_once_with("task:lock:catalog-sync", "1", nx=True, ex=30)

    def test_task_lock_redis_failure_is_fail_closed(self):
        with patch.object(redis_support, "require_redis", side_effect=redis_support.RedisUnavailable):
            with self.assertRaises(redis_support.RedisUnavailable):
                redis_support.acquire_task_lock("catalog-sync", 30)

    def test_require_redis_translates_connection_errors(self):
        client = Mock()
        client.ping.side_effect = redis.ConnectionError("unavailable")
        with patch.object(redis_support, "get_redis", return_value=client):
            with self.assertRaises(redis_support.RedisUnavailable):
                redis_support.require_redis()


if __name__ == "__main__":
    unittest.main()