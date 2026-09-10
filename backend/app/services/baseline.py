import math


def probabilita_poisson(lam, gol):
    if lam <= 0:
        return 1.0 if gol == 0 else 0.0

    return (
        math.exp(-lam)
        * (lam ** gol)
        / math.factorial(gol)
    )


def stima_gol_attesi(
    casa_gol_fatti,
    casa_gol_subiti,
    ospite_gol_fatti,
    ospite_gol_subiti,
    media_campionato,
    partite_storiche_casa=1,
    partite_storiche_ospite=1
):
    """
    Modello base con stabilizzazione verso la media del campionato.

    Con poche partite, le medie estreme vengono riportate
    parzialmente verso la media generale del campionato.
    """

    if media_campionato <= 0:
        media_campionato = 1.0

    def stabilizza(media_squadra, numero_partite):
        numero_partite = max(numero_partite, 0)

        return (
            numero_partite * media_squadra
            + media_campionato
        ) / (numero_partite + 1)

    casa_attacco = stabilizza(
        casa_gol_fatti,
        partite_storiche_casa
    )

    casa_difesa = stabilizza(
        casa_gol_subiti,
        partite_storiche_casa
    )

    ospite_attacco = stabilizza(
        ospite_gol_fatti,
        partite_storiche_ospite
    )

    ospite_difesa = stabilizza(
        ospite_gol_subiti,
        partite_storiche_ospite
    )

    gol_attesi_casa = (
        casa_attacco
        * ospite_difesa
        / media_campionato
    )

    gol_attesi_ospite = (
        ospite_attacco
        * casa_difesa
        / media_campionato
    )

    return (
        round(gol_attesi_casa, 4),
        round(gol_attesi_ospite, 4)
    )

def genera_griglia_probabilita(
    gol_attesi_casa,
    gol_attesi_ospite,
    massimo_gol=10
):
    risultati = []

    for gol_casa in range(massimo_gol + 1):
        for gol_ospite in range(massimo_gol + 1):

            probabilita = (
                probabilita_poisson(
                    gol_attesi_casa,
                    gol_casa
                )
                *
                probabilita_poisson(
                    gol_attesi_ospite,
                    gol_ospite
                )
            )

            risultati.append({
                "gol_casa": gol_casa,
                "gol_ospite": gol_ospite,
                "probabilita": probabilita
            })

    return risultati
