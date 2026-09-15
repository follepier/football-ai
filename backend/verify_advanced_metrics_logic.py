from app.services.advanced_stats import (
    calculate_team_advanced_metrics_from_league_data,
)


def main():
    league_data = {
        "teams": {
            "1": {
                "title": "Alpha FC",
                "history": [
                    {
                        "ppda": {"att": 80, "def": 10},
                        "deep": 12,
                        "deep_allowed": 8,
                    },
                    {
                        "ppda": {"att": 70, "def": 10},
                        "deep": 8,
                        "deep_allowed": 12,
                    },
                ],
            }
        },
        "players": [
            {
                "team_title": "Alpha FC",
                "xA": "1.2",
                "key_passes": "5",
            },
            {
                "team_title": "Alpha FC",
                "xA": "0.8",
                "key_passes": "3",
            },
            {
                "team_title": "Other FC",
                "xA": "99",
                "key_passes": "99",
            },
        ],
    }

    metrics = calculate_team_advanced_metrics_from_league_data(
        league_data,
        "Alpha FC",
    )

    assert metrics["matches"] == 2
    assert metrics["ppda"] == 7.5
    assert metrics["expected_assists_per_match"] == 1.0
    assert metrics["key_passes_per_match"] == 4.0
    assert metrics["deep_completions_per_match"] == 10.0
    assert metrics["deep_allowed_per_match"] == 10.0
    assert metrics["field_tilt_proxy"] == 50.0
    assert metrics["field_tilt_status"] == "proxy_in_audit"

    print("PASS advanced metrics deterministic logic")


if __name__ == "__main__":
    main()
