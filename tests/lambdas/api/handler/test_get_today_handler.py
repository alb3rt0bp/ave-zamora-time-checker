import json
import unittest
from unittest.mock import patch

from tests.dummies.api_handler_test_case import ApiHandlerTestCase
from tests.dummies.frozen_datetime import make_frozen_datetime
from tests.dummies.reference_dates import MONDAY
from tests.dummies.time_utils import madrid_time_to_utc

TODAY_ISO = MONDAY.isoformat()
OTHER_DAY_ISO = "2026-01-06"


class FakeContext:
    aws_request_id = "get-today-test"


class TestGetTodayHandler(ApiHandlerTestCase):
    def _frozen(self):
        return make_frozen_datetime(madrid_time_to_utc(MONDAY, 10, 0))

    def test_returns_empty_list_when_no_trains_seeded(self):
        with patch("api_handler.datetime", self._frozen()):
            response = self.handler.get_today_handler({}, FakeContext())

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"]), [])

    def test_returns_projected_trains_for_today_only(self):
        self.put_state_item({
            "pk": f"04154#{TODAY_ISO}",
            "cod_comercial": "04154",
            "sentido": "Madrid",
            "tipo_dia": "laborable",
            "hora_programada": "07:41",
            "hora_llegada_corregida": "07:47",
            "ult_retraso": 6,
            "capturado_en_zamora": True,
            "entregado": True,
            "updated_at": "2026-01-05T07:47:23+01:00",
        })
        self.put_state_item({
            "pk": f"04200#{OTHER_DAY_ISO}",
            "cod_comercial": "04200",
            "sentido": "Galicia",
            "tipo_dia": "laborable",
            "hora_programada": "08:00",
            "ult_retraso": 0,
            "capturado_en_zamora": False,
            "entregado": False,
            "updated_at": "2026-01-06T08:00:00+01:00",
        })

        with patch("api_handler.datetime", self._frozen()):
            response = self.handler.get_today_handler({}, FakeContext())

        body = json.loads(response["body"])
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["cod_comercial"], "04154")
        self.assertNotIn("pk", body[0])

    def test_excludes_seed_marker_item(self):
        self.put_state_item({"pk": f"SEED#{TODAY_ISO}", "ttl": 0})

        with patch("api_handler.datetime", self._frozen()):
            response = self.handler.get_today_handler({}, FakeContext())

        self.assertEqual(json.loads(response["body"]), [])


if __name__ == "__main__":
    unittest.main()
