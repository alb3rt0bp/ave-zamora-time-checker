import unittest

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA
from tests.dummies.reference_dates import MONDAY, SUNDAY
from tests.dummies.gtfs_samples import GTFS_FILES, ZAMORA_CODE, CHAMARTIN_CODE

from gtfs_schedule_builder import build_todays_trains


class TestBuildTodaysTrains(unittest.TestCase):
    def _build(self, target_date):
        return build_todays_trains(GTFS_FILES, target_date, ZAMORA_CODE, CHAMARTIN_CODE, SAMPLE_LOG_EXTRA)

    def _by_cod(self, trains, cod_comercial):
        return next(t for t in trains if t["cod_comercial"] == cod_comercial)

    def test_madrid_train_resolved_with_zamora_departure_and_chamartin_arrival(self):
        train = self._by_cod(self._build(MONDAY), "04154")

        self.assertEqual(
            train,
            {
                "cod_comercial": "04154",
                "sentido": "Madrid",
                "tipo_dia": "laborable",
                "weekdays": [0, 1, 2, 3, 4],
                "hora_salida": "07:41",
                "hora_llegada_destino": "08:49",
                "offset_dias_salida": 0,
                "offset_dias_llegada": 0,
            },
        )

    def test_train_arriving_past_midnight_keeps_the_day_it_belongs_to(self):
        # TRIP_MNIGHT llega a Chamartín a las "24:10" en GTFS: la hora de
        # reloj es 00:10, pero de un día después que la salida. Sin ese
        # offset, ScheduleMatcher cerraría su ventana a las 00:20 del mismo
        # día de la salida y el tren se volcaría siempre como 'cancelado'.
        train = self._by_cod(self._build(MONDAY), "04777")

        self.assertEqual(train["hora_salida"], "23:05")
        self.assertEqual(train["offset_dias_salida"], 0)
        self.assertEqual(train["hora_llegada_destino"], "00:10")
        self.assertEqual(train["offset_dias_llegada"], 1)

    def test_galicia_train_only_active_on_its_calendar_dates_exception(self):
        monday_trains = self._build(MONDAY)
        sunday_trains = self._build(SUNDAY)

        self.assertNotIn("04505", [t["cod_comercial"] for t in monday_trains])

        train = self._by_cod(sunday_trains, "04505")
        self.assertEqual(train["sentido"], "Galicia")
        self.assertEqual(train["hora_salida"], "10:04")  # salida de Chamartín
        self.assertEqual(train["hora_llegada_destino"], "11:08")  # llegada a Zamora
        self.assertEqual(train["tipo_dia"], "domingo")

    def test_double_composition_dedupes_to_a_single_entry(self):
        trains = [t for t in self._build(MONDAY) if t["cod_comercial"] == "04999"]

        self.assertEqual(len(trains), 1)

    def test_trip_without_chamartin_stop_is_excluded(self):
        codes = [t["cod_comercial"] for t in self._build(MONDAY)]

        self.assertNotIn("04001", codes)

    def test_trip_without_trip_short_name_is_excluded(self):
        # No tiene cod_comercial en absoluto, así que no puede aparecer bajo
        # ningún código — solo comprobamos que no revienta ni cuela vacío.
        trains = self._build(MONDAY)

        self.assertTrue(all(t["cod_comercial"] for t in trains))

    def test_calendar_dates_exception_removes_a_normally_active_service(self):
        codes = [t["cod_comercial"] for t in self._build(MONDAY)]

        self.assertNotIn("04222", codes)

    def test_service_outside_calendar_date_range_is_excluded(self):
        codes = [t["cod_comercial"] for t in self._build(MONDAY)]

        self.assertNotIn("04333", codes)

    def test_result_is_sorted_by_sentido_then_hora_salida(self):
        trains = self._build(MONDAY)

        keys = [(t["sentido"], t["hora_salida"]) for t in trains]
        self.assertEqual(keys, sorted(keys))


if __name__ == "__main__":
    unittest.main()
