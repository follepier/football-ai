import unittest

from app.services import team_data


class TeamDataTests(unittest.TestCase):
    def test_calcola_medie_partite_computes_all_metrics(self):
        matches = [
            {
                "gol_fatti": 2,
                "gol_subiti": 1,
                "corner": 6,
                "ammonizioni": 2,
                "possesso": 60,
                "tiri_in_porta": 5,
                "tiri_fuori": 7,
                "attacchi": 100,
                "attacchi_pericolosi": 40,
            },
            {
                "gol_fatti": 0,
                "gol_subiti": 1,
                "corner": 4,
                "ammonizioni": 4,
                "possesso": 50,
                "tiri_in_porta": 3,
                "tiri_fuori": 5,
                "attacchi": 80,
                "attacchi_pericolosi": 30,
            },
        ]

        result = team_data.calcola_medie_partite(matches)

        self.assertEqual(result["gol_fatti"], 1.0)
        self.assertEqual(result["gol_subiti"], 1.0)
        self.assertEqual(result["corner"], 5.0)
        self.assertEqual(result["ammonizioni"], 3.0)
        self.assertEqual(result["possesso"], 55.0)
        self.assertEqual(result["tiri_in_porta"], 4.0)
        self.assertEqual(result["tiri_fuori"], 6.0)
        self.assertEqual(result["attacchi"], 90.0)
        self.assertEqual(result["attacchi_pericolosi"], 35.0)

    def test_empty_average_has_complete_schema(self):
        result = team_data.calcola_medie_partite([])
        expected_keys = {
            "gol_fatti",
            "gol_subiti",
            "corner",
            "ammonizioni",
            "possesso",
            "tiri_in_porta",
            "tiri_fuori",
            "attacchi",
            "attacchi_pericolosi",
        }

        self.assertEqual(set(result), expected_keys)
        self.assertTrue(all(value == 0 for value in result.values()))

    def test_home_away_filter_uses_only_requested_context(self):
        matches = [
            {
                "casa_trasferta": "casa",
                "gol_fatti": 3,
                "gol_subiti": 1,
                "corner": 8,
                "ammonizioni": 1,
                "possesso": 62,
                "tiri_in_porta": 7,
                "tiri_fuori": 8,
                "attacchi": 110,
                "attacchi_pericolosi": 50,
            },
            {
                "casa_trasferta": "trasferta",
                "gol_fatti": 0,
                "gol_subiti": 2,
                "corner": 2,
                "ammonizioni": 3,
                "possesso": 40,
                "tiri_in_porta": 2,
                "tiri_fuori": 4,
                "attacchi": 70,
                "attacchi_pericolosi": 20,
            },
        ]

        home = team_data.calcola_medie_casa_trasferta(matches, "casa")
        away = team_data.calcola_medie_casa_trasferta(matches, "trasferta")

        self.assertEqual(home["gol_fatti"], 3.0)
        self.assertEqual(home["possesso"], 62.0)
        self.assertEqual(away["gol_fatti"], 0.0)
        self.assertEqual(away["possesso"], 40.0)

    def test_shrinkage_with_zero_matches_returns_league_mean(self):
        self.assertEqual(
            team_data.shrinkage_media(
                media_squadra=3.0,
                numero_partite=0,
                media_campionato=1.5,
                varianza_tra_squadre=0.2,
                varianza_osservazioni=1.0,
            ),
            1.5,
        )

    def test_shrinkage_with_zero_observation_variance_returns_team_mean(self):
        self.assertEqual(
            team_data.shrinkage_media(
                media_squadra=2.1,
                numero_partite=4,
                media_campionato=1.5,
                varianza_tra_squadre=0.2,
                varianza_osservazioni=0.0,
            ),
            2.1,
        )

    def test_shrinkage_stays_between_team_and_league_means(self):
        value = team_data.shrinkage_media(
            media_squadra=2.5,
            numero_partite=5,
            media_campionato=1.5,
            varianza_tra_squadre=0.2,
            varianza_osservazioni=1.0,
        )
        self.assertGreaterEqual(value, 1.5)
        self.assertLessEqual(value, 2.5)


if __name__ == "__main__":
    unittest.main()
