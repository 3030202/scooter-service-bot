import unittest

from app.services.catalog import SEED_CATALOG


class TestCatalogSeed(unittest.TestCase):
    def test_seed_catalog_has_core_service_groups(self):
        codes = {item["code"] for item in SEED_CATALOG}
        self.assertTrue({"battery_diag", "controller_repair", "tire_tube", "brake_service", "display_throttle"}.issubset(codes))

    def test_seed_catalog_items_have_price_and_checklist(self):
        for item in SEED_CATALOG:
            self.assertGreater(item["base_price"], 0)
            self.assertTrue(item["keywords"])
            self.assertTrue(item["checklist"])

