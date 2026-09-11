from fastapi import FastAPI, HTTPException

from app.services.team_data import (
    crea_dati_squadra,
    calcola_medie_casa_trasferta,
)
from app.services.football_api import (
    get_team_last_matches,
    trasforma_partite_squadra,
)
from app.services.analysis import calcola_analisi

app = FastAPI(
    title="Football AI",
    version="0.5.0",
    description="Motore di analisi statistica e probabilistica delle partite di calcio.",
)


@app.get("/")
def root():
    return {
        "app": "Football AI",
        "status": "online",
        "version": "0.5.0",
        "engine": "statistical-probabilistic",
    }


@app.get("/health")
def health():
    return {"status": "healthy", "version": "0.5.0"}


@app.get("/analyze")
def analyze(casa: str = "", ospite: str = ""):
    casa = casa.strip()
    ospite = ospite.strip()

    if not casa or not ospite:
        raise HTTPException(
            status_code=400,
            detail="Inserisci sia la squadra di casa sia la squadra ospite.",
        )

    if casa.lower() == ospite.lower():
        raise HTTPException(
            status_code=400,
            detail="Le due squadre devono essere diverse.",
        )

    partite_casa = get_team_last_matches(casa)
    partite_ospite = get_team_last_matches(ospite)

    ultime_partite_casa = trasforma_partite_squadra(
        partite_casa,
        casa,
    )
    ultime_partite_ospite = trasforma_partite_squadra(
        partite_ospite,
        ospite,
    )

    if not ultime_partite_casa:
        raise HTTPException(
            status_code=404,
            detail=f"Nessuna partita recente trovata per {casa}.",
        )

    if not ultime_partite_ospite:
        raise HTTPException(
            status_code=404,
            detail=f"Nessuna partita recente trovata per {ospite}.",
        )

    medie_casa = calcola_medie_casa_trasferta(
        ultime_partite_casa,
        "casa",
    )
    medie_ospite = calcola_medie_casa_trasferta(
        ultime_partite_ospite,
        "trasferta",
    )

    dati_casa = crea_dati_squadra(
        casa,
        ultime_partite_casa,
        medie_casa["gol_fatti"],
        medie_casa["gol_subiti"],
        medie_casa["corner"],
        medie_casa["ammonizioni"],
        medie_casa["possesso"],
        medie_casa["tiri_in_porta"],
        medie_casa["tiri_fuori"],
        medie_casa["attacchi"],
        medie_casa["attacchi_pericolosi"],
    )

    dati_ospite = crea_dati_squadra(
        ospite,
        ultime_partite_ospite,
        medie_ospite["gol_fatti"],
        medie_ospite["gol_subiti"],
        medie_ospite["corner"],
        medie_ospite["ammonizioni"],
        medie_ospite["possesso"],
        medie_ospite["tiri_in_porta"],
        medie_ospite["tiri_fuori"],
        medie_ospite["attacchi"],
        medie_ospite["attacchi_pericolosi"],
    )

    risultato = calcola_analisi(dati_casa, dati_ospite)

    return {
        "status": "success",
        "partita": f"{casa} vs {ospite}",
        "analisi": risultato,
        "ultime_partite": {
            "casa": ultime_partite_casa,
            "ospite": ultime_partite_ospite,
        },
    }
