import unittest

from tests.dummies import tweet_notifier_env  # noqa: F401 - sys.path setup
import claude_client


class TestTweetLength(unittest.TestCase):
    def test_counts_text_blank_line_and_hashtags(self):
        length = claude_client.tweet_length("hola", ["#A", "#B"])
        self.assertEqual(length, len("hola\n\n#A #B"))

    def test_counts_text_alone_when_no_hashtags(self):
        self.assertEqual(claude_client.tweet_length("hola", []), len("hola\n\n"))


if __name__ == "__main__":
    unittest.main()
