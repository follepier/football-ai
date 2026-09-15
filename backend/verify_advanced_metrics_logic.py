from app.services.advanced_stats import (
    build_shot_heatmap,
    calculate_team_advanced_metrics_from_league_data,
    is_inside_penalty_area,
    saved_shots_inside_box,
)
from app.services.shot_extras import calculate_shot_extras_from_shots


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
    assert metrics["field_tilt_status"] == "proxy_published"

    shots = [
        {
            "X": "0.90",
            "Y": "0.50",
            "result": "SavedShot",
            "xG": "0.40",
            "situation": "OpenPlay",
        },
        {
            "X": "0.84",
            "Y": "0.25",
            "result": "SavedShot",
            "xG": "0.20",
            "situation": "FromCorner",
        },
        {
            "X": "0.70",
            "Y": "0.50",
            "result": "SavedShot",
            "xG": "0.10",
            "situation": "OpenPlay",
        },
        {
            "X": "0.90",
            "Y": "0.10",
            "result": "SavedShot",
            "xG": "0.05",
            "situation": "SetPiece",
        },
        {
            "X": "0.90",
            "Y": "0.50",
            "result": "Goal",
            "xG": "0.30",
            "situation": "OpenPlay",
        },
    ]

    assert is_inside_penalty_area(shots[0]) is True
    assert is_inside_penalty_area(shots[2]) is False
    assert saved_shots_inside_box(shots) == 2

    heatmap = build_shot_heatmap(shots, columns=4, rows=2)
    assert heatmap["columns"] == 4
    assert heatmap["rows"] == 2
    assert heatmap["shots"] == 5
    assert heatmap["xg_total"] == 1.05
    assert heatmap["xg_per_shot"] == 0.21
    assert len(heatmap["cells"]) == 8
    assert max(cell["intensity"] for cell in heatmap["cells"]) == 1.0

    profile = heatmap["profile"]
    assert profile["shots_inside_box"] == 3
    assert profile["shots_inside_box_share_pct"] == 60.0
    assert profile["xg_inside_box"] == 0.9
    assert profile["shots_outside_box"] == 2
    assert profile["shots_outside_box_share_pct"] == 40.0
    assert profile["xg_outside_box"] == 0.15
    assert profile["lateral_distribution"]["left"]["shots"] == 2
    assert profile["lateral_distribution"]["left"]["share_pct"] == 40.0
    assert profile["lateral_distribution"]["center"]["shots"] == 3
    assert profile["lateral_distribution"]["center"]["share_pct"] == 60.0
    assert profile["lateral_distribution"]["right"]["shots"] == 0
    assert profile["situations"][0]["situation"] == "OpenPlay"
    assert profile["situations"][0]["shots"] == 3
    assert profile["situations"][0]["share_pct"] == 60.0

    extras = calculate_shot_extras_from_shots(shots, matches_used=2)
    assert extras["goals"] == 1
    assert extras["xg_total"] == 1.05
    assert extras["non_penalty_xg"] == 1.05
    assert extras["non_penalty_xg_per_match"] == 0.53
    assert extras["goals_minus_xg"] == -0.05
    assert extras["set_piece_xg"] == 0.25
    assert extras["set_piece_xg_share_pct"] == 23.8
    assert extras["average_shot_distance_m"] == 21.1
    assert extras["distance_shots"] == 5

    penalty_shots = shots + [
        {
            "X": "0.885",
            "Y": "0.50",
            "result": "Goal",
            "xG": "0.76",
            "situation": "Penalty",
        }
    ]
    penalty_extras = calculate_shot_extras_from_shots(
        penalty_shots,
        matches_used=2,
    )
    assert penalty_extras["xg_total"] == 1.81
    assert penalty_extras["non_penalty_xg"] == 1.05
    assert penalty_extras["non_penalty_xg_per_match"] == 0.53
    assert penalty_extras["set_piece_xg"] == 0.25

    print("PASS advanced metrics deterministic logic")


if __name__ == "__main__":
    main()
