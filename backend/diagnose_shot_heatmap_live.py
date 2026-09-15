import argparse

from app.services.advanced_stats import (
    _get_match_shots,
    _recent_finished_team_matches,
    _shot_coordinates,
    build_shot_heatmap,
)
from app.services.football_api import (
    get_understat_league_data,
    stessa_squadra,
)


def _sample_keys(shots):
    if not shots:
        return []
    return sorted(shots[0].keys())


def diagnose_team(competition, team_name, limit=5):
    league_data = get_understat_league_data(competition)
    matches = _recent_finished_team_matches(
        league_data,
        team_name,
        limit=limit,
    )

    print(f"\n=== {team_name} ({competition}) ===")
    print(f"recent_finished_matches={len(matches)}")

    collected = []

    for match in matches:
        home = (match.get("h") or {}).get("title")
        away = (match.get("a") or {}).get("title")
        shots = _get_match_shots(match["id"])

        if home and stessa_squadra(team_name, home):
            side = "home"
            own_shots = shots["home"]
        elif away and stessa_squadra(team_name, away):
            side = "away"
            own_shots = shots["away"]
        else:
            side = "unmatched"
            own_shots = []

        valid_coordinates = sum(
            1 for shot in own_shots if _shot_coordinates(shot) is not None
        )

        print(
            {
                "match_id": match.get("id"),
                "home": home,
                "away": away,
                "team_side": side,
                "home_shots": len(shots["home"]),
                "away_shots": len(shots["away"]),
                "own_shots": len(own_shots),
                "valid_coordinates": valid_coordinates,
                "sample_keys": _sample_keys(own_shots),
            }
        )

        if own_shots:
            first = own_shots[0]
            print(
                "first_shot_sample=",
                {
                    "X": first.get("X"),
                    "Y": first.get("Y"),
                    "x": first.get("x"),
                    "y": first.get("y"),
                    "xG": first.get("xG"),
                    "xg": first.get("xg"),
                    "h_a": first.get("h_a"),
                    "h_team": first.get("h_team"),
                    "a_team": first.get("a_team"),
                    "result": first.get("result"),
                },
            )

        collected.extend(own_shots)

    heatmap = build_shot_heatmap(collected)
    print(
        "heatmap_summary=",
        {
            "raw_shots": len(collected),
            "valid_shots": heatmap["shots"],
            "xg_total": heatmap["xg_total"],
            "xg_per_shot": heatmap["xg_per_shot"],
        },
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--competition", default="serie-a")
    parser.add_argument("--teams", nargs="+", required=True)
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    for team_name in args.teams:
        diagnose_team(
            args.competition,
            team_name,
            limit=max(1, min(args.limit, 10)),
        )


if __name__ == "__main__":
    main()
