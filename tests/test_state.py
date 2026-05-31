from datetime import datetime, timezone
import unittest

from nodestrap.state import mark_host_completed, mark_host_failed


class StateTests(unittest.TestCase):
    def test_mark_host_completed(self):
        data = {"hosts": [{"host": "node.example.com", "status": "new", "last_error": "old"}]}
        completed_at = datetime(2026, 5, 31, 12, 0, tzinfo=timezone.utc)

        mark_host_completed(data, "node.example.com", completed_at=completed_at)

        self.assertEqual("completed", data["hosts"][0]["status"])
        self.assertEqual("2026-05-31T12:00:00+00:00", data["hosts"][0]["completed_at"])
        self.assertIsNone(data["hosts"][0]["last_error"])

    def test_mark_host_failed_retryable(self):
        data = {"hosts": [{"host": "node.example.com", "status": "new"}]}

        mark_host_failed(data, "node.example.com", error="sudo validation failed")

        self.assertEqual("retry", data["hosts"][0]["status"])
        self.assertEqual("sudo validation failed", data["hosts"][0]["last_error"])


if __name__ == "__main__":
    unittest.main()

