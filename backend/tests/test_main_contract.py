import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app import main


COMPLETE_AVERAGES = {
    "gol_fatti": 1.0,
    "gol_subiti": 1.0,
    "corner": 4.0,
    "ammonizioni": 2.0,
    "possesso": 50.0,
    "tiri_in_porta": 4.0,
    "tiri_fuori": 6.0,
    "attacchi": 80.0,
    "attacchi_pericolosi": 30.0,
}


class MainContractTests(unittest.TestCase):
    def test_analyze_requires_both_teams(self):
        for casa, ospite in [("", "milan"), ("inter", ""), (" ", "milan")]:
            with self.subTest(casa=casa, ospite=ospite):
                with self.assertRaises(HTTPException) as ctx:
                    main.analyze(casa, ospite)
                self.assertEqual(ctx.exception.status_code, 400)

    def test_analyze_rejects_same_literal_team_case_insensitively(self):
        with self.assertRaises(HTTPException) as ctx:
            main.analyze("Inter", "inter")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_analyze_rejects_aliases_of_same_team(self):
        # Contract expected after introducing canonical team matching.
        # At present main.py compares only lower-cased strings, so aliases
        # such as "milan" and "AC Milan" can slip through as two teams.
        raw = [{"id": 1}]
        transformed = [{"casa_trasferta": "casa"}]

        for casa, ospite in [
            ("milan", "AC Milan"),
            ("inter", "Inter Milan"),
        ]:
            with self.subTest(casa=casa, ospite=ospite):
                with patch.object(
                    main,
                    "get_team_last_matches",
                    return_value=raw,
                ), patch.object(
                    main,
                    "trasforma_partite_squadra",
                    return_value=transformed,
                ), patch.object(
                    main,
                    "calcola_medie_casa_trasferta",
                    return_value=COMPLETE_AVERAGES,
                ), patch.object(
                    main,
                    "crea_dati_squadra",
                    side_effect=lambda nome, *_args: {"nome": nome},
                ), patch.object(
                    main,
                    "calcola_analisi",
                    return_value={"sentinel": 123},
                ):
                    with self.assertRaises(HTTPException) as ctx:
                        main.analyze(casa, ospite)
                self.assertEqual(ctx.exception.status_code, 400)

    def test_analyze_returns_404_when_home_team_has_no_recent_matches(self):
        with patch.object(main, "get_team_last_matches", side_effect=[[], [object()]]):
            with patch.object(main, "trasforma_partite_squadra", side_effect=[[], [{"ok": True}]]):
                with self.assertRaises(HTTPException) as ctx:
                    main.analyze("inter", "milan")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_analyze_success_response_contract(self):
        raw_home = [{"id": 1}]
        raw_away = [{"id": 2}]
        transformed_home = [{"casa_trasferta": "casa", "marker": "home"}]
        transformed_away = [{"casa_trasferta": "trasferta", "marker": "away"}]

        with patch.object(
            main,
            "get_team_last_matches",
            side_effect=[raw_home, raw_away],
        ), patch.object(
            main,
            "trasforma_partite_squadra",
            side_effect=[transformed_home, transformed_away],
        ), patch.object(
            main,
            "calcola_medie_casa_trasferta",
            return_value=COMPLETE_AVERAGES,
        ), patch.object(
            main,
            "crea_dati_squadra",
            side_effect=lambda nome, *_args: {"nome": nome},
        ), patch.object(
            main,
            "calcola_analisi",
            return_value={"sentinel": 123},
        ):
            result = main.analyze(" inter ", " milan ")

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["partita"], "inter vs milan")
        self.assertEqual(result["analisi"], {"sentinel": 123})
        self.assertEqual(result["ultime_partite"]["casa"], transformed_home)
        self.assertEqual(result["ultime_partite"]["ospite"], transformed_away)


if __name__ == "__main__":
    unittest.main()
