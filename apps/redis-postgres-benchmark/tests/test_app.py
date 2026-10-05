import datetime
import unittest

from app import app, normalize_value, percentile, summarize_timings


class BenchmarkAppTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_dashboard_renders(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"PostgreSQL", response.data)
        self.assertIn(b"Redis", response.data)

    def test_benchmark_rejects_out_of_range_iterations(self):
        response = self.client.post("/api/benchmark", json={"iterations": 2})
        self.assertEqual(response.status_code, 400)

    def test_timestamp_normalization_matches_json_cache_value(self):
        timestamp = datetime.datetime(2026, 10, 1, 12, 30)
        self.assertEqual(
            normalize_value({"created_at": timestamp}),
            {"created_at": "2026-10-01T12:30:00"},
        )

    def test_percentile_and_timing_summary(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        summary = summarize_timings(values)
        self.assertEqual(percentile(values, 0.95), 5.0)
        self.assertEqual(summary["median_ms"], 3.0)
        self.assertEqual(summary["min_ms"], 1.0)
        self.assertEqual(summary["max_ms"], 5.0)


if __name__ == "__main__":
    unittest.main()