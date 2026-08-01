import unittest

from tests.dummies.api_handler_test_case import ApiHandlerTestCase

TARGET_DATE_ISO = "2026-01-05"
OTHER_DATE_ISO = "2026-01-06"


class TestScanTrainsForDate(ApiHandlerTestCase):
    def test_returns_empty_list_for_empty_table(self):
        result = self.handler._scan_trains_for_date(TARGET_DATE_ISO)

        self.assertEqual(result, [])

    def test_returns_only_items_for_target_date(self):
        self.put_state_item({"pk": f"04154#{TARGET_DATE_ISO}", "cod_comercial": "04154"})
        self.put_state_item({"pk": f"04200#{OTHER_DATE_ISO}", "cod_comercial": "04200"})

        result = self.handler._scan_trains_for_date(TARGET_DATE_ISO)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["cod_comercial"], "04154")

    def test_excludes_seed_marker_item(self):
        self.put_state_item({"pk": f"SEED#{TARGET_DATE_ISO}", "ttl": 0})
        self.put_state_item({"pk": f"04154#{TARGET_DATE_ISO}", "cod_comercial": "04154"})

        result = self.handler._scan_trains_for_date(TARGET_DATE_ISO)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["cod_comercial"], "04154")


if __name__ == "__main__":
    unittest.main()
