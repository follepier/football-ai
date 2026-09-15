from collections import defaultdict

from app.services.competitions import COMPETITIONS
from app.services.football_api import (
    get_competition_teams,
    get_understat_league_data,
    normalizza_nome_squadra,
    stessa_squadra,
)


def understat_teams(competizione):
    dati = get_understat_league_data(competizione)
    squadre = set()

    for partita in dati.get("dates", []):
        casa = partita.get("h", {}).get("title")
        ospite = partita.get("a", {}).get("title")

        if casa:
            squadre.add(casa)
        if ospite:
            squadre.add(ospite)

    return sorted(squadre, key=str.casefold)


def trova_match(nome, candidati):
    for candidato in candidati:
        if stessa_squadra(nome, candidato):
            return candidato
    return None


def audit_competizione(slug):
    provider = get_competition_teams(slug)
    understat = understat_teams(slug)

    duplicati = defaultdict(list)
    for nome in provider:
        duplicati[normalizza_nome_squadra(nome)].append(nome)

    provider_non_match = []
    mapping = []

    for nome in provider:
        match = trova_match(nome, understat)
        if match is None:
            provider_non_match.append(nome)
        else:
            mapping.append((nome, match))

    understat_non_match = []
    for nome in understat:
        match = trova_match(nome, provider)
        if match is None:
            understat_non_match.append(nome)

    print("\n" + "=" * 72)
    print(f"{COMPETITIONS[slug]['name']} ({slug})")
    print("=" * 72)
    print(f"Provider:  {len(provider)} nomi")
    print(f"Understat: {len(understat)} nomi")
    print(f"Match:      {len(mapping)}")

    print("\nMAPPING TROVATI")
    for provider_name, understat_name in mapping:
        marker = "=" if provider_name == understat_name else "->"
        print(f"  {provider_name} {marker} {understat_name}")

    print("\nPROVIDER SENZA MATCH UNDERSTAT")
    if provider_non_match:
        for nome in provider_non_match:
            print(f"  - {nome}")
    else:
        print("  nessuno")

    print("\nUNDERSTAT SENZA MATCH PROVIDER")
    if understat_non_match:
        for nome in understat_non_match:
            print(f"  - {nome}")
    else:
        print("  nessuno")

    print("\nPOSSIBILI DUPLICATI PROVIDER DOPO NORMALIZZAZIONE")
    trovati = False
    for canonico, nomi in sorted(duplicati.items()):
        if len(nomi) > 1:
            trovati = True
            print(f"  - {canonico}: {nomi}")
    if not trovati:
        print("  nessuno")


if __name__ == "__main__":
    for competition_slug in (
        "premier-league",
        "la-liga",
        "bundesliga",
        "ligue-1",
    ):
        audit_competizione(competition_slug)
