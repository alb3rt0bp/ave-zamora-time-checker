import unittest
from unittest.mock import patch

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

    def test_follows_pagination_across_multiple_scan_pages(self):
        self.put_state_item({"pk": f"04154#{TARGET_DATE_ISO}", "cod_comercial": "04154"})
        self.put_state_item({"pk": f"04475#{TARGET_DATE_ISO}", "cod_comercial": "04475"})

        first_page = {
            "Items": [{"pk": f"04154#{TARGET_DATE_ISO}", "cod_comercial": "04154"}],
            "LastEvaluatedKey": {"pk": f"04154#{TARGET_DATE_ISO}"},
        }
        second_page = {"Items": [{"pk": f"04475#{TARGET_DATE_ISO}", "cod_comercial": "04475"}]}

        with patch.object(self.handler.state_table, "scan", side_effect=[first_page, second_page]) as mock_scan:
            result = self.handler._scan_trains_for_date(TARGET_DATE_ISO)

        self.assertEqual(mock_scan.call_count, 2)
        self.assertEqual(mock_scan.call_args_list[1].kwargs["ExclusiveStartKey"], {"pk": f"04154#{TARGET_DATE_ISO}"})
        self.assertEqual({item["cod_comercial"] for item in result}, {"04154", "04475"})


if __name__ == "__main__":
    unittest.main()
