import unittest
from unittest.mock import patch

from tests.dummies.api_handler_test_case import ApiHandlerTestCase


class TestScanMetricsByPrefix(ApiHandlerTestCase):
    def test_returns_empty_list_when_no_items_match(self):
        result = self.handler._scan_metrics_by_prefix("TRAIN#")

        self.assertEqual(result, [])

    def test_returns_only_items_matching_prefix(self):
        self.put_metrics_item({"pk": "TRAIN#04154"})
        self.put_metrics_item({"pk": "WEEK#2026-W02"})

        result = self.handler._scan_metrics_by_prefix("TRAIN#")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["pk"], "TRAIN#04154")

    def test_follows_pagination_across_multiple_scan_pages(self):
        first_page = {"Items": [{"pk": "TRAIN#04154"}], "LastEvaluatedKey": {"pk": "TRAIN#04154"}}
        second_page = {"Items": [{"pk": "TRAIN#04475"}]}

        with patch.object(self.handler.metrics_table, "scan", side_effect=[first_page, second_page]) as mock_scan:
            result = self.handler._scan_metrics_by_prefix("TRAIN#")

        self.assertEqual(mock_scan.call_count, 2)
        self.assertEqual(mock_scan.call_args_list[1].kwargs["ExclusiveStartKey"], {"pk": "TRAIN#04154"})
        self.assertEqual({item["pk"] for item in result}, {"TRAIN#04154", "TRAIN#04475"})


if __name__ == "__main__":
    unittest.main()
