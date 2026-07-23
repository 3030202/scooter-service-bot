import unittest

from app.services.metrics import RuntimeMetrics


class TestMetrics(unittest.TestCase):
    def test_metrics_render_prometheus(self):
        metrics = RuntimeMetrics()
        metrics.inc("tickets_done_total")
        rendered = metrics.render_prometheus()
        self.assertIn("scooter_bot_uptime_seconds", rendered)
        self.assertIn("scooter_bot_tickets_done_total 1", rendered)

