import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA
from tests.dummies.reference_dates import MONDAY

TZ = ZoneInfo("Europe/Madrid")
NOW = datetime(MONDAY.year, MONDAY.month, MONDAY.day, 5, 0, tzinfo=TZ)
TODAY = NOW.date()

TRAINS_TODAY = [
    {
        "cod_comercial": "M100", "sentido": "Madrid", "tipo_dia": "laborable",
        "hora_salida": "07:00", "hora_llegada_destino": "08:30",
    },
    {
        "cod_comercial": "G100", "sentido": "Galicia", "tipo_dia": "laborable",
        "hora_salida": "08:00", "hora_llegada_destino": "09:30",
    },
]


class TestSeedTodaysTrains(HandlerTestCase):
    """
    _seed_todays_trains ya no decide qué trenes son "de hoy" — eso es
    responsabilidad de schedule_resolver.py (con sus propios tests). Aquí se
    le pasa ya la lista resuelta, tal y como haría lambda_handler.
    """

    def test_seeds_placeholder_for_each_train_received(self):
        self.handler._seed_todays_trains(TODAY, NOW, TRAINS_TODAY, SAMPLE_LOG_EXTRA)

        self.assertIsNotNone(self.get_item("M100", "2026-01-05"))
        self.assertIsNotNone(self.get_item("G100", "2026-01-05"))

    def test_placeholder_shape(self):
        self.handler._seed_todays_trains(TODAY, NOW, TRAINS_TODAY, SAMPLE_LOG_EXTRA)

        item = self.get_item("M100", "2026-01-05")
        self.assertEqual(item["sentido"], "Madrid")
        self.assertEqual(item["tipo_dia"], "laborable")
        self.assertEqual(item["hora_programada"], "08:30")
        self.assertEqual(item["ult_retraso"], 0)
        self.assertFalse(item["capturado_en_zamora"])
        self.assertFalse(item["entregado"])
        self.assertIn("ttl", item)

    def test_creates_seed_marker_with_the_seeding_timestamp(self):
        self.handler._seed_todays_trains(TODAY, NOW, TRAINS_TODAY, SAMPLE_LOG_EXTRA)

        marker = self.table.get_item(Key={"pk": "SEED#2026-01-05"}).get("Item")
        self.assertIsNotNone(marker)
        # daily_dump_handler usa 'seeded_at' para distinguir un día sembrado
        # el propio día de uno resembrado a posteriori (ver _check_seed_marker).
        self.assertEqual(marker["seeded_at"], NOW.isoformat())

    def test_second_call_is_a_noop(self):
        self.handler._seed_todays_trains(TODAY, NOW, TRAINS_TODAY, SAMPLE_LOG_EXTRA)
        # Simula progreso real tras el primer sembrado.
        self.table.update_item(
            Key={"pk": f"M100#2026-01-05"},
            UpdateExpression="SET ult_retraso = :v",
            ExpressionAttributeValues={":v": 12},
        )

        self.handler._seed_todays_trains(TODAY, NOW, TRAINS_TODAY, SAMPLE_LOG_EXTRA)

        item = self.get_item("M100", "2026-01-05")
        self.assertEqual(item["ult_retraso"], 12)  # no se ha vuelto a pisar con el placeholder

    def test_does_not_seed_outside_the_days_own_calendar_day(self):
        # Regresión del 2026-09-18: en el tramo de madrugada el día operativo
        # sigue siendo el de ayer. Si su marcador ya no está (TTL), sembrar
        # no recupera nada — reescribe el día entero como placeholders sin
        # entregar, que el volcado de las 02:15 lee como cancelaciones.
        night_tail_now = datetime(
            TODAY.year, TODAY.month, TODAY.day, 0, 30, tzinfo=TZ
        ) + timedelta(days=1)

        self.handler._seed_todays_trains(TODAY, night_tail_now, TRAINS_TODAY, SAMPLE_LOG_EXTRA)

        self.assertIsNone(self.get_item("M100", "2026-01-05"))
        self.assertIsNone(self.get_item("G100", "2026-01-05"))
        self.assertIsNone(self.table.get_item(Key={"pk": "SEED#2026-01-05"}).get("Item"))

    def test_alerts_when_seeding_is_blocked_outside_the_day(self):
        night_tail_now = datetime(
            TODAY.year, TODAY.month, TODAY.day, 0, 30, tzinfo=TZ
        ) + timedelta(days=1)

        self.handler._seed_todays_trains(TODAY, night_tail_now, TRAINS_TODAY, SAMPLE_LOG_EXTRA)

        alerts = self.get_published_data_quality_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertIn("Sembrado fuera de día", alerts[0]["subject"])

    def test_alerts_when_the_marker_is_gone_but_the_day_had_progress(self):
        # El marcador no debería desaparecer antes que los trenes del día: si
        # pasa, nada se sobrescribe (el PutItem es condicional) pero hay que
        # enterarse, porque apunta a un TTL demasiado corto.
        self.table.put_item(Item={
            "pk": "M100#2026-01-05", "entregado": True, "ult_retraso": 12,
        })

        self.handler._seed_todays_trains(TODAY, NOW, TRAINS_TODAY, SAMPLE_LOG_EXTRA)

        item = self.get_item("M100", "2026-01-05")
        self.assertTrue(item["entregado"])
        alerts = self.get_published_data_quality_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertIn("Marcador de sembrado ausente", alerts[0]["subject"])

    def test_does_not_alert_when_preexisting_items_are_just_placeholders(self):
        # Dos ejecuciones solapadas del primer ciclo del día: los items del
        # otro sembrado son placeholders idénticos, no hay nada que avisar.
        self.table.put_item(Item={
            "pk": "M100#2026-01-05", "entregado": False, "ult_retraso": 0,
        })

        self.handler._seed_todays_trains(TODAY, NOW, TRAINS_TODAY, SAMPLE_LOG_EXTRA)

        self.assertEqual(self.get_published_data_quality_alerts(), [])

    def test_does_not_overwrite_preexisting_item_even_without_marker(self):
        # Defensa ante ejecuciones solapadas: si el item ya existe pero el
        # marcador aún no se ha escrito, el PutItem condicional no debe pisarlo.
        self.table.put_item(Item={"pk": "M100#2026-01-05", "entregado": True, "ult_retraso": 99})

        self.handler._seed_todays_trains(TODAY, NOW, TRAINS_TODAY, SAMPLE_LOG_EXTRA)

        item = self.get_item("M100", "2026-01-05")
        self.assertTrue(item["entregado"])
        self.assertEqual(item["ult_retraso"], 99)


if __name__ == "__main__":
    unittest.main()
