def crea_dati_squadra(
    nome,
    ultime_partite,
    gol_fatti,
    gol_subiti,
    corner_medi,
    ammonizioni_medie,
    possesso_medio=0,
    tiri_in_porta_medi=0,
    tiri_fuori_medi=0,
    attacchi_medi=0,
    attacchi_pericolosi_medi=0
):
    return {
        "nome": nome,
        "ultime_partite": ultime_partite,
        "gol_fatti": gol_fatti,
        "gol_subiti": gol_subiti,
        "corner_medi": corner_medi,
        "ammonizioni_medie": ammonizioni_medie,
        "possesso_medio": possesso_medio,
        "tiri_in_porta_medi": tiri_in_porta_medi,
        "tiri_fuori_medi": tiri_fuori_medi,
        "attacchi_medi": attacchi_medi,
        "attacchi_pericolosi_medi": attacchi_pericolosi_medi
    }


def calcola_medie_partite(partite):
    if not partite:
        return {
            "gol_fatti": 0,
            "gol_subiti": 0,
            "corner": 0,
            "ammonizioni": 0
        }

    numero_partite = len(partite)

    return {
        "gol_fatti": round(
            sum(p["gol_fatti"] for p in partite) / numero_partite, 2
        ),
        "gol_subiti": round(
            sum(p["gol_subiti"] for p in partite) / numero_partite, 2
        ),
        "corner": round(
            sum(p["corner"] for p in partite) / numero_partite, 2
        ),
        "ammonizioni": round(
            sum(p["ammonizioni"] for p in partite) / numero_partite, 2
        ),
        "possesso": round(
            sum(p["possesso"] for p in partite) / numero_partite, 2
        ),
        "tiri_in_porta": round(
            sum(p["tiri_in_porta"] for p in partite) / numero_partite, 2
        ),
        "tiri_fuori": round(
            sum(p["tiri_fuori"] for p in partite) / numero_partite, 2
        ),
        "attacchi": round(
            sum(p["attacchi"] for p in partite) / numero_partite, 2
        ),
        "attacchi_pericolosi": round(
            sum(p["attacchi_pericolosi"] for p in partite) / numero_partite, 2
        )
    }


def calcola_medie_casa_trasferta(partite, tipo):
    partite_filtrate = [
        p for p in partite
        if p.get("casa_trasferta") == tipo
    ]

    return calcola_medie_partite(partite_filtrate)


def shrinkage_media(media_squadra, numero_partite, media_campionato,
                     varianza_tra_squadre, varianza_osservazioni):
    """
    Stima shrinkage empirico-bayesiana.

    Il peso della media della squadra dipende dalla quantità
    e dalla variabilità dei dati, senza usare pesi arbitrari.
    """

    if numero_partite <= 0:
        return round(media_campionato, 4)

    if varianza_osservazioni <= 0:
        return round(media_squadra, 4)

    peso = (
        numero_partite * varianza_tra_squadre
        / (
            numero_partite * varianza_tra_squadre
            + varianza_osservazioni
        )
    )

    return round(
        media_campionato
        + peso * (media_squadra - media_campionato),
        4
    )
