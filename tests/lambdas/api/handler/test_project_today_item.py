import unittest

from tests.dummies import api_env


class TestProjectTodayItem(unittest.TestCase):
    def setUp(self):
        self.handler = api_env.import_api_handler()

    def test_whitelists_public_fields_only(self):
        item = {
            "pk": "04154#2026-01-05",
            "cod_comercial": "04154",
            "sentido": "Madrid",
            "tipo_dia": "laborable",
            "hora_programada": "07:41",
            "hora_llegada_corregida": "07:47",
            "hora_paso_zamora": "07:03",
            "ult_retraso": 6,
            "capturado_en_zamora": True,
            "entregado": True,
            "updated_at": "2026-01-05T07:47:23+01:00",
            "ttl": 1767654600,
        }

        projected = self.handler._project_today_item(item)

        self.assertEqual(
            projected,
            {
                "cod_comercial": "04154",
                "sentido": "Madrid",
                "tipo_dia": "laborable",
                "hora_programada": "07:41",
                "hora_llegada_corregida": "07:47",
                "hora_paso_zamora": "07:03",
                "ult_retraso": 6,
                "capturado_en_zamora": True,
                "entregado": True,
                "updated_at": "2026-01-05T07:47:23+01:00",
            },
        )

    def test_handles_placeholder_item_with_missing_optional_fields(self):
        item = {
            "pk": "04154#2026-01-05",
            "cod_comercial": "04154",
            "sentido": "Madrid",
            "tipo_dia": "laborable",
            "hora_programada": "07:41",
            "ult_retraso": 0,
            "capturado_en_zamora": False,
            "entregado": False,
            "updated_at": "2026-01-05T07:00:00+01:00",
        }

        projected = self.handler._project_today_item(item)

        self.assertNotIn("pk", projected)
        self.assertIsNone(projected.get("hora_llegada_corregida"))
        self.assertIsNone(projected.get("hora_paso_zamora"))


if __name__ == "__main__":
    unittest.main()
