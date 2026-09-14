DEFAULT_COMPETITION = "serie-a"

COMPETITIONS = {
    "serie-a": {
        "slug": "serie-a",
        "name": "Serie A",
        "country": "Italia",
        "provider_league_id": 3405541143,
        "understat_league": "Serie_A",
        "model_validated": True,
    },
    "premier-league": {
        "slug": "premier-league",
        "name": "Premier League",
        "country": "Inghilterra",
        "provider_league_id": 4160026622,
        "understat_league": "EPL",
        "model_validated": False,
    },
    "la-liga": {
        "slug": "la-liga",
        "name": "La Liga",
        "country": "Spagna",
        "provider_league_id": 4212821298,
        "understat_league": "La_liga",
        "model_validated": False,
    },
    "bundesliga": {
        "slug": "bundesliga",
        "name": "Bundesliga",
        "country": "Germania",
        "provider_league_id": 686337048,
        "understat_league": "Bundesliga",
        "model_validated": False,
    },
    "ligue-1": {
        "slug": "ligue-1",
        "name": "Ligue 1",
        "country": "Francia",
        "provider_league_id": 3614399544,
        "understat_league": "Ligue_1",
        "model_validated": False,
    },
}

COMPETITION_ALIASES = {
    "serie a": "serie-a",
    "serie-a": "serie-a",
    "italy serie a": "serie-a",
    "premier": "premier-league",
    "premier league": "premier-league",
    "premier-league": "premier-league",
    "epl": "premier-league",
    "la liga": "la-liga",
    "la-liga": "la-liga",
    "laliga": "la-liga",
    "bundesliga": "bundesliga",
    "ligue 1": "ligue-1",
    "ligue-1": "ligue-1",
    "ligue1": "ligue-1",
}


def normalizza_competizione(value):
    if value is None:
        return DEFAULT_COMPETITION

    valore = str(value).strip().lower()
    if not valore:
        return DEFAULT_COMPETITION

    return COMPETITION_ALIASES.get(valore, valore)


def get_competition_config(value=DEFAULT_COMPETITION):
    slug = normalizza_competizione(value)

    if slug not in COMPETITIONS:
        raise ValueError(f"Competizione non supportata: {value}")

    return COMPETITIONS[slug]


def list_competitions():
    return [
        {
            "slug": config["slug"],
            "name": config["name"],
            "country": config["country"],
            "model_validated": config["model_validated"],
        }
        for config in COMPETITIONS.values()
    ]
