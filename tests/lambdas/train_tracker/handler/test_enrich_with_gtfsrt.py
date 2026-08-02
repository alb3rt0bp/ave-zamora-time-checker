import unittest
from unittest.mock import patch

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA
from tests.dummies.fake_http import fake_urlopen_json, raise_url_error
from tests.dummies.gtfsrt_samples import ENTITY_M100, ENTITY_G100, ENTITY_UNRELATED

ZAMORA_CODE = "30200"
CHAMARTIN_CODE = "17000"


class TestFetchGtfsrtEntities(HandlerTestCase):
    @patch("handler.GTFS_RT_ENRICHMENT_ENABLED", False)
    @patch("urllib.request.urlopen")
    def test_flag_disabled_returns_empty_list_without_fetching(self, mock_urlopen):
        result = self.handler._fetch_gtfsrt_entities(SAMPLE_LOG_EXTRA)

        self.assertEqual(result, [])
        mock_urlopen.assert_not_called()

    @patch("handler.GTFS_RT_ENRICHMENT_ENABLED", True)
    @patch("urllib.request.urlopen", side_effect=raise_url_error)
    def test_fetch_failure_returns_empty_list(self, mock_urlopen):
        result = self.handler._fetch_gtfsrt_entities(SAMPLE_LOG_EXTRA)

        self.assertEqual(result, [])

    @patch("handler.GTFS_RT_ENRICHMENT_ENABLED", True)
    @patch("urllib.request.urlopen")
    def test_fetch_success_returns_entities(self, mock_urlopen):
        mock_urlopen.return_value = fake_urlopen_json({"entity": [ENTITY_M100]})

        result = self.handler._fetch_gtfsrt_entities(SAMPLE_LOG_EXTRA)

        self.assertEqual(result, [ENTITY_M100])


class TestEnrichWithGtfsrt(HandlerTestCase):
    @patch("handler.GTFS_RT_ENRICHMENT_ENABLED", False)
    @patch("urllib.request.urlopen")
    def test_returns_empty_dict_when_flag_disabled(self, mock_urlopen):
        result = self.handler._enrich_with_gtfsrt("M100", "Madrid", CHAMARTIN_CODE, SAMPLE_LOG_EXTRA)

        self.assertEqual(result, {})
        mock_urlopen.assert_not_called()

    @patch("handler.GTFS_RT_ENRICHMENT_ENABLED", True)
    @patch("urllib.request.urlopen", side_effect=raise_url_error)
    def test_never_raises_when_fetch_fails(self, mock_urlopen):
        result = self.handler._enrich_with_gtfsrt("M100", "Madrid", CHAMARTIN_CODE, SAMPLE_LOG_EXTRA)

        self.assertEqual(result, {})

    @patch("handler.GTFS_RT_ENRICHMENT_ENABLED", True)
    @patch("urllib.request.urlopen")
    def test_returns_empty_dict_when_no_match(self, mock_urlopen):
        mock_urlopen.return_value = fake_urlopen_json({"entity": [ENTITY_UNRELATED]})

        result = self.handler._enrich_with_gtfsrt("M100", "Madrid", CHAMARTIN_CODE, SAMPLE_LOG_EXTRA)

        self.assertEqual(result, {})

    @patch("handler.GTFS_RT_ENRICHMENT_ENABLED", True)
    @patch("urllib.request.urlopen")
    def test_galicia_train_mirrors_hora_paso_zamora_gtfsrt(self, mock_urlopen):
        # Sentido Galicia: Zamora ES la estación final del sentido, así que
        # hora_paso_zamora_gtfsrt debe coincidir con hora_llegada_gtfsrt
        # (mismo evento) — igual que ya ocurre con hora_paso_zamora hoy.
        mock_urlopen.return_value = fake_urlopen_json({"entity": [ENTITY_G100]})

        result = self.handler._enrich_with_gtfsrt("G100", "Galicia", ZAMORA_CODE, SAMPLE_LOG_EXTRA)

        self.assertEqual(result["hora_llegada_gtfsrt"], result["hora_paso_zamora_gtfsrt"])
        self.assertEqual(result["minutos_retraso_gtfsrt"], 0)

    @patch("handler.GTFS_RT_ENRICHMENT_ENABLED", True)
    @patch("urllib.request.urlopen")
    def test_madrid_train_gets_chamartin_fields_and_zamora_bonus(self, mock_urlopen):
        # ENTITY_M100 trae stopTimeUpdate tanto de Chamartín como de Zamora
        # en el mismo trip: un tren Madrid debe recibir ambos sin una
        # segunda petición HTTP (misma lista de entidades ya descargada).
        mock_urlopen.return_value = fake_urlopen_json({"entity": [ENTITY_M100]})

        result = self.handler._enrich_with_gtfsrt("M100", "Madrid", CHAMARTIN_CODE, SAMPLE_LOG_EXTRA)

        self.assertEqual(result["minutos_retraso_gtfsrt"], 5)   # Chamartín: 300s
        self.assertEqual(result["hora_llegada_gtfsrt"], "09:15")  # Chamartín
        self.assertEqual(result["hora_paso_zamora_gtfsrt"], "08:34")  # Zamora (bonus)
        self.assertEqual(mock_urlopen.call_count, 1)


if __name__ == "__main__":
    unittest.main()
