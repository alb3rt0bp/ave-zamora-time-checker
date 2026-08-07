import unittest

from tests.dummies import tweet_notifier_env  # noqa: F401 - sys.path setup
import claude_client

ALERT = {
    "cod_comercial": "04154",
    "sentido": "Madrid",
    "hora_programada": "08:56",
    "hora_llegada_corregida": "09:16",
    "minutos_retraso": 20,
    "fecha": "2026-08-03",
    "es_tren_madrugador": True,
}


class TestBuildUserMessage(unittest.TestCase):
    def test_includes_situacion_and_train_data(self):
        message = claude_client._build_user_message(ALERT, [])

        self.assertIn("Situación: tren_madrugador_con_retraso", message)
        self.assertIn("04154", message)
        self.assertIn("Madrid", message)
        self.assertIn("08:56", message)
        self.assertIn("09:16", message)
        self.assertIn("20", message)
        self.assertIn("2026-08-03", message)

    def test_includes_trending_hashtags_when_present(self):
        message = claude_client._build_user_message(ALERT, ["#Algo", "#OtraCosa"])

        self.assertIn("#Algo, #OtraCosa", message)

    def test_omits_trending_line_when_empty(self):
        message = claude_client._build_user_message(ALERT, [])

        self.assertNotIn("Tendencias actuales", message)


if __name__ == "__main__":
    unittest.main()
