import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA
from tests.dummies.reference_dates import MONDAY

TZ = ZoneInfo("Europe/Madrid")
NOW = datetime(MONDAY.year, MONDAY.month, MONDAY.day, 8, 45, tzinfo=TZ)

SCHEDULED = {
    "cod_comercial": "M100",
    "sentido": "Madrid",
    "tipo_dia": "laborable",
    "hora_llegada_destino": "08:30",
}

# "04154" es el FLAGSHIP_MADRID_TRAIN_CODE por defecto (ver handler.py) — el
# primer tren laborable hacia Madrid, eje de la reivindicación del tren
# madrugador. Publica alerta siempre, tenga o no retraso.
FLAGSHIP_SCHEDULED = {
    "cod_comercial": "04154",
    "sentido": "Madrid",
    "tipo_dia": "laborable",
    "hora_llegada_destino": "08:56",
}


class TestMaybePublishDelayAlert(HandlerTestCase):
    def test_does_not_publish_at_threshold(self):
        # DELAY_ALERT_THRESHOLD_MINUTES=15 en el entorno de test: 15 no supera el umbral.
        self.handler._maybe_publish_delay_alert(SCHEDULED, 15, "08:45", NOW, SAMPLE_LOG_EXTRA)

        self.assertEqual(self.get_published_delay_alerts(), [])

    def test_does_not_publish_below_threshold(self):
        self.handler._maybe_publish_delay_alert(SCHEDULED, 5, "08:35", NOW, SAMPLE_LOG_EXTRA)

        self.assertEqual(self.get_published_delay_alerts(), [])

    def test_publishes_above_threshold(self):
        self.handler._maybe_publish_delay_alert(SCHEDULED, 16, "08:46", NOW, SAMPLE_LOG_EXTRA)

        alerts = self.get_published_delay_alerts()
        self.assertEqual(len(alerts), 1)

    def test_publishes_expected_payload(self):
        self.handler._maybe_publish_delay_alert(SCHEDULED, 20, "08:50", NOW, SAMPLE_LOG_EXTRA)

        [alert] = self.get_published_delay_alerts()
        self.assertEqual(alert, {
            "cod_comercial": "M100",
            "sentido": "Madrid",
            "hora_programada": "08:30",
            "hora_llegada_corregida": "08:50",
            "minutos_retraso": 20,
            "fecha": NOW.date().isoformat(),
            "es_tren_madrugador": False,
        })

    def test_flagship_train_publishes_even_with_zero_delay(self):
        self.handler._maybe_publish_delay_alert(FLAGSHIP_SCHEDULED, 0, "08:56", NOW, SAMPLE_LOG_EXTRA)

        alerts = self.get_published_delay_alerts()
        self.assertEqual(len(alerts), 1)

    def test_flagship_train_payload_marks_es_tren_madrugador(self):
        self.handler._maybe_publish_delay_alert(FLAGSHIP_SCHEDULED, 20, "09:16", NOW, SAMPLE_LOG_EXTRA)

        [alert] = self.get_published_delay_alerts()
        self.assertEqual(alert, {
            "cod_comercial": "04154",
            "sentido": "Madrid",
            "hora_programada": "08:56",
            "hora_llegada_corregida": "09:16",
            "minutos_retraso": 20,
            "fecha": NOW.date().isoformat(),
            "es_tren_madrugador": True,
        })


if __name__ == "__main__":
    unittest.main()
