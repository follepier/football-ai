import csv
import sys

sys.path.insert(0, ".")

from app.services.baseline import stima_gol_attesi


FILE = "../data/serie_a_features.csv"


def numero(valore):
    if valore in ("", None):
        return None
    return float(valore)


with open(FILE, encoding="utf-8") as f:
    partite = list(csv.DictReader(f))


risultati = []

for partita in partite:

    casa_gf = numero(partita["casa_gol_fatti_totale_pre"])
    casa_gs = numero(partita["casa_gol_subiti_totale_pre"])
    casa_xgf = numero(partita["casa_xg_fatti_totale_pre"])
    casa_xgs = numero(partita["casa_xg_subiti_totale_pre"])

    ospite_gf = numero(partita["ospite_gol_fatti_totale_pre"])
    ospite_gs = numero(partita["ospite_gol_subiti_totale_pre"])
    ospite_xgf = numero(partita["ospite_xg_fatti_totale_pre"])
    ospite_xgs = numero(partita["ospite_xg_subiti_totale_pre"])

    storico_casa = int(partita["casa_partite_totale_pre"])
    storico_ospite = int(partita["ospite_partite_totale_pre"])

    if (
        casa_gf is None
        or casa_gs is None
        or ospite_gf is None
        or ospite_gs is None
    ):
        continue

    media_campionato = 1.5

    gol_casa_attesi, gol_ospite_attesi = stima_gol_attesi(
        casa_gf,
        casa_gs,
        ospite_gf,
        ospite_gs,
        media_campionato,
        storico_casa,
        storico_ospite
    )

    risultati.append({
        "data": partita["data"],
        "casa": partita["casa"],
        "ospite": partita["ospite"],
        "gol_casa_reali": int(partita["gol_casa"]),
        "gol_ospite_reali": int(partita["gol_ospite"]),
        "gol_casa_attesi": gol_casa_attesi,
        "gol_ospite_attesi": gol_ospite_attesi,
        "storico_casa": storico_casa,
        "storico_ospite": storico_ospite
    })


with open(
    "../data/serie_a_backtest_baseline.csv",
    "w",
    newline="",
    encoding="utf-8"
) as f:

    campi = risultati[0].keys()
    writer = csv.DictWriter(f, fieldnames=campi)

    writer.writeheader()
    writer.writerows(risultati)


print("Backtest baseline creato correttamente")
print("Partite utilizzate:", len(risultati))
print("File:", "../data/serie_a_backtest_baseline.csv")
