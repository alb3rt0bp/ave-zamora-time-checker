import unittest

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA

from datalake_writer import DatalakeWriter


class TestDatalakeWriterInit(unittest.TestCase):
    def test_stores_bucket_and_client_and_log_extra(self):
        fake_s3 = object()

        writer = DatalakeWriter(fake_s3, "my-bucket", SAMPLE_LOG_EXTRA)

        self.assertIs(writer.s3, fake_s3)
        self.assertEqual(writer.bucket, "my-bucket")
        self.assertEqual(writer.log_extra, SAMPLE_LOG_EXTRA)


if __name__ == "__main__":
    unittest.main()
