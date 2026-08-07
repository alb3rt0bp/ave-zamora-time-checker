import unittest

from tests.dummies import tweet_notifier_env  # noqa: F401 - sys.path setup
import claude_client

BASE_ALERT = {
    "cod_comercial": "04154",
    "sentido": "Madrid",
    "hora_programada": "08:56",
    "hora_llegada_corregida": "08:56",
    "fecha": "2026-08-03",
}


class TestSituacion(unittest.TestCase):
    def test_tren_madrugador_con_retraso(self):
        alert = {**BASE_ALERT, "es_tren_madrugador": True, "minutos_retraso": 20}
        self.assertEqual(claude_client._situacion(alert), "tren_madrugador_con_retraso")

    def test_tren_madrugador_puntual(self):
        alert = {**BASE_ALERT, "es_tren_madrugador": True, "minutos_retraso": 0}
        self.assertEqual(claude_client._situacion(alert), "tren_madrugador_puntual")

    def test_tren_madrugador_en_el_umbral_es_puntual(self):
        alert = {**BASE_ALERT, "es_tren_madrugador": True, "minutos_retraso": 15}
        self.assertEqual(claude_client._situacion(alert), "tren_madrugador_puntual")

    def test_retraso_generico_para_otros_trenes(self):
        alert = {**BASE_ALERT, "cod_comercial": "M100", "es_tren_madrugador": False, "minutos_retraso": 20}
        self.assertEqual(claude_client._situacion(alert), "retraso_generico")

    def test_retraso_generico_si_falta_el_campo_es_tren_madrugador(self):
        alert = {**BASE_ALERT, "minutos_retraso": 20}
        self.assertEqual(claude_client._situacion(alert), "retraso_generico")


if __name__ == "__main__":
    unittest.main()
