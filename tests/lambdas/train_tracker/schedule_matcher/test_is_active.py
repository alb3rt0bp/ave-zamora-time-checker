import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA
from tests.dummies.reference_dates import MONDAY

from schedule_matcher import ScheduleMatcher

TZ = ZoneInfo("Europe/Madrid")

MADRID_TRAIN = {
    "cod_comercial": "M100",
    "sentido": "Madrid",
    "tipo_dia": "laborable",
    "hora_salida": "07:00",
    "hora_llegada_destino": "08:30",
}

GALICIA_TRAIN = {
    "cod_comercial": "G100",
    "sentido": "Galicia",
    "tipo_dia": "laborable",
    "hora_salida": "08:00",
    "hora_llegada_destino": "09:30",
}

# Sale de Zamora a las 23:50 y llega a Chamartín a las 00:40 del día
# SIGUIENTE (en GTFS, "24:40" — ver gtfs_schedule_builder._day_offset).
MADRID_TRAIN_PAST_MIDNIGHT = {
    "cod_comercial": "M900",
    "sentido": "Madrid",
    "tipo_dia": "laborable",
    "hora_salida": "23:50",
    "hora_llegada_destino": "00:40",
    "offset_dias_salida": 0,
    "offset_dias_llegada": 1,
}


def _at(hh, mm):
    return datetime(MONDAY.year, MONDAY.month, MONDAY.day, hh, mm, tzinfo=TZ)


class TestIsActive(unittest.TestCase):
    def setUp(self):
        self.matcher = ScheduleMatcher({"trains": []}, SAMPLE_LOG_EXTRA)

    def test_madrid_inactive_before_window_start(self):
        # hora_salida - 1h = 06:00
        self.assertFalse(self.matcher._is_active(MADRID_TRAIN, _at(5, 59), None))

    def test_madrid_active_exactly_at_window_start(self):
        self.assertTrue(self.matcher._is_active(MADRID_TRAIN, _at(6, 0), None))

    def test_madrid_active_without_state_lookup_until_10min_after_arrival(self):
        # hora_llegada_destino (08:30) + 0 retraso + 10 min = 08:40
        self.assertTrue(self.matcher._is_active(MADRID_TRAIN, _at(8, 40), None))
        self.assertFalse(self.matcher._is_active(MADRID_TRAIN, _at(8, 41), None))

    def test_madrid_window_extends_with_known_delay(self):
        lookup = lambda cod: {"ult_retraso": 20}
        # 08:30 + 20 + 10 = 09:00
        self.assertTrue(self.matcher._is_active(MADRID_TRAIN, _at(9, 0), lookup))
        self.assertFalse(self.matcher._is_active(MADRID_TRAIN, _at(9, 1), lookup))

    def test_madrid_state_lookup_returning_none_assumes_zero_delay(self):
        lookup = lambda cod: None
        self.assertTrue(self.matcher._is_active(MADRID_TRAIN, _at(8, 40), lookup))
        self.assertFalse(self.matcher._is_active(MADRID_TRAIN, _at(8, 41), lookup))

    def test_galicia_active_with_no_upper_bound(self):
        self.assertTrue(self.matcher._is_active(GALICIA_TRAIN, _at(23, 55), None))

    def test_galicia_inactive_before_window_start(self):
        # hora_salida - 1h = 07:00
        self.assertFalse(self.matcher._is_active(GALICIA_TRAIN, _at(6, 59), None))

    def test_madrid_train_arriving_past_midnight_is_active_all_evening(self):
        # Ventana desde 22:50 (23:50 - 1h) hasta las 00:50 del día siguiente.
        # Sin offset_dias_llegada, la llegada se anclaría a las 00:40 de ESTE
        # mismo día y la ventana estaría cerrada desde primera hora: el tren
        # no se monitorizaría nunca y se volcaría como 'cancelado'.
        self.assertFalse(self.matcher._is_active(MADRID_TRAIN_PAST_MIDNIGHT, _at(22, 49), None))
        self.assertTrue(self.matcher._is_active(MADRID_TRAIN_PAST_MIDNIGHT, _at(22, 50), None))
        self.assertTrue(self.matcher._is_active(MADRID_TRAIN_PAST_MIDNIGHT, _at(23, 59), None))

    def test_matcher_no_longer_applies_once_past_midnight(self):
        # Pasada la medianoche el matcher ancla ya en el día calendario
        # NUEVO, así que este tren de "ayer" le sale inactivo (su ventana
        # empezaría esta noche a las 22:50). No es un fallo: a esas horas
        # manda el tramo de madrugada, que ignora ventanas y reintenta
        # cualquier tren del día operativo aún sin resolver
        # (handler._get_pending_trains).
        past_midnight = _at(0, 20) + timedelta(days=1)

        self.assertFalse(self.matcher._is_active(MADRID_TRAIN_PAST_MIDNIGHT, past_midnight, None))

    def test_a_train_without_offsets_behaves_as_before(self):
        # El fichero estático de reserva no trae estos campos: el matcher
        # debe seguir funcionando exactamente igual sin ellos.
        self.assertNotIn("offset_dias_llegada", MADRID_TRAIN)
        self.assertTrue(self.matcher._is_active(MADRID_TRAIN, _at(8, 40), None))
        self.assertFalse(self.matcher._is_active(MADRID_TRAIN, _at(8, 41), None))


if __name__ == "__main__":
    unittest.main()
