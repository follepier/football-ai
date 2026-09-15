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


def _media_opzionale(partite, campo):
    valori = []

    for partita in partite:
        valore = partita.get(campo)
        if valore is None:
            continue

        try:
            numero = float(valore)
        except (TypeError, ValueError):
            continue

        valori.append(numero)

    if not valori:
        # Manteniamo compatibilita' con il motore, ma esponiamo separatamente
        # il numero di campioni: il chiamante puo' distinguere 0 reale da dato
        # indisponibile e non mostrarlo come statistica osservata.
        return 0, 0

    return round(sum(valori) / len(valori), 2), len(valori)


def calcola_medie_partite(partite):
    if not partite:
        return {
            "gol_fatti": 0,
            "gol_subiti": 0,
            "corner": 0,
            "ammonizioni": 0,
            "possesso": 0,
            "tiri_in_porta": 0,
            "tiri_fuori": 0,
            "attacchi": 0,
            "attacchi_pericolosi": 0,
            "possesso_campioni": 0,
            "tiri_in_porta_campioni": 0,
            "tiri_fuori_campioni": 0,
            "attacchi_campioni": 0,
            "attacchi_pericolosi_campioni": 0,
        }

    numero_partite = len(partite)

    possesso, possesso_campioni = _media_opzionale(partite, "possesso")
    tiri_in_porta, tiri_in_porta_campioni = _media_opzionale(
        partite,
        "tiri_in_porta",
    )
    tiri_fuori, tiri_fuori_campioni = _media_opzionale(
        partite,
        "tiri_fuori",
    )
    attacchi, attacchi_campioni = _media_opzionale(partite, "attacchi")
    attacchi_pericolosi, attacchi_pericolosi_campioni = _media_opzionale(
        partite,
        "attacchi_pericolosi",
    )

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
        "possesso": possesso,
        "tiri_in_porta": tiri_in_porta,
        "tiri_fuori": tiri_fuori,
        "attacchi": attacchi,
        "attacchi_pericolosi": attacchi_pericolosi,
        "possesso_campioni": possesso_campioni,
        "tiri_in_porta_campioni": tiri_in_porta_campioni,
        "tiri_fuori_campioni": tiri_fuori_campioni,
        "attacchi_campioni": attacchi_campioni,
        "attacchi_pericolosi_campioni": attacchi_pericolosi_campioni,
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

    Il peso della media della squadra dipende dalla quantita
    e dalla variabilita dei dati, senza usare pesi arbitrari.
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
