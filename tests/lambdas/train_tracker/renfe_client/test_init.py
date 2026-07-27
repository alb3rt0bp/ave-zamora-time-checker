import unittest

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA

from renfe_client import RenfeClient


class TestRenfeClientInit(unittest.TestCase):
    def test_default_timeout(self):
        client = RenfeClient(SAMPLE_LOG_EXTRA)
        self.assertEqual(client.timeout, 15)

    def test_custom_timeout(self):
        client = RenfeClient(SAMPLE_LOG_EXTRA, timeout_seconds=5)
        self.assertEqual(client.timeout, 5)

    def test_stores_log_extra(self):
        client = RenfeClient(SAMPLE_LOG_EXTRA)
        self.assertEqual(client.log_extra, SAMPLE_LOG_EXTRA)


if __name__ == "__main__":
    unittest.main()
