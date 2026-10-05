import unittest
from unittest.mock import Mock, patch

from tokapp_collector.models import ProcessStats
from tokapp_collector.runner import Runner


class RunnerTests(unittest.TestCase):
    def test_first_error_is_reported_even_with_less_than_an_hour_of_uptime(self) -> None:
        service = Mock()
        service.process_once.return_value = ProcessStats(errors=["temporary failure"])
        publisher = Mock()
        runner = Runner(service, publisher, 180)

        with patch("tokapp_collector.runner.time.monotonic", side_effect=[30, 60, 3630]):
            runner.run_once()
            self.assertEqual(publisher.publish_error.call_count, 1)
            runner.run_once()
            self.assertEqual(publisher.publish_error.call_count, 1)
            runner.run_once()
            self.assertEqual(publisher.publish_error.call_count, 2)


if __name__ == "__main__":
    unittest.main()
