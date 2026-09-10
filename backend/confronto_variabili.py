import csv
import math

FEATURES = "../data/serie_a_features.csv"
BASELINE = "../data/serie_a_backtest_baseline.csv"


def numero(v):
    if v in ("", None):
        return None
    return float(v)


def mae(reali, pred):
    return sum(abs(a - b) for a, b in zip(reali, pred)) / len(reali)


def rmse(reali, pred):
    return math.sqrt(
        sum((a - b) ** 2 for a, b in zip(reali, pred)) / len(reali)
    )


# -----------------------------
# CARICAMENTO DATI
# -----------------------------

with open(FEATURES, encoding="utf-8") as f:
    features = list(csv.DictReader(f))

with open(BASELINE, encoding="utf-8") as f:
    baseline = list(csv.DictReader(f))


indice = {
    (r["data"], r["casa"], r["ospite"]): r
    for r in features
}


partite = []

for b in baseline:
    chiave = (b["data"], b["casa"], b["ospite"])
    f = indice.get(chiave)

    if f is None:
        continue

    partite.append({
        "data": b["data"],
        "casa": b["casa"],
        "ospite": b["ospite"],
        "gol_casa": float(b["gol_casa_reali"]),
        "gol_ospite": float(b["gol_ospite_reali"]),

        "baseline_casa": float(b["gol_casa_attesi"]),
        "baseline_ospite": float(b["gol_ospite_attesi"]),

        "possesso_casa": numero(f["casa_possesso_totale_pre"]),
        "possesso_ospite": numero(f["ospite_possesso_totale_pre"]),

        "tiri_casa": numero(f["casa_tiri_in_porta_totale_pre"]),
        "tiri_ospite": numero(f["ospite_tiri_in_porta_totale_pre"]),
    })


print("\n===== CONFRONTO VARIABILI =====")
print(f"Partite comuni al baseline: {len(partite)}")


# -----------------------------
# BASELINE
# -----------------------------

reali_casa = [p["gol_casa"] for p in partite]
reali_ospite = [p["gol_ospite"] for p in partite]

base_casa = [p["baseline_casa"] for p in partite]
base_ospite = [p["baseline_ospite"] for p in partite]

base_mae = (
    mae(reali_casa, base_casa)
    + mae(reali_ospite, base_ospite)
) / 2

base_rmse = (
    rmse(reali_casa, base_casa)
    + rmse(reali_ospite, base_ospite)
) / 2

print(f"\nBASELINE")
print(f"MAE medio:  {base_mae:.4f}")
print(f"RMSE medio: {base_rmse:.4f}")


# -----------------------------
# ANALISI SEMPLICE DELLA VARIABILE
# -----------------------------
#
# Per evitare di inventare pesi, calcoliamo soltanto
# la relazione statistica tra la variabile e l'errore
# del baseline.
#
# Non modifichiamo ancora le predizioni.
# Questo serve a capire se la variabile contiene
# informazione utile prima di inserirla nel modello.
# -----------------------------


def analizza_variabile(nome, valori_casa, valori_ospite):

    dati = []

    for i, p in enumerate(partite):

        if valori_casa[i] is None or valori_ospite[i] is None:
            continue

        errore_casa = abs(
            p["gol_casa"] - p["baseline_casa"]
        )

        errore_ospite = abs(
            p["gol_ospite"] - p["baseline_ospite"]
        )

        errore = (errore_casa + errore_ospite) / 2

        differenza = valori_casa[i] - valori_ospite[i]

        dati.append((differenza, errore))

    if len(dati) < 5:
        print(f"\n{nome}")
        print("Dati insufficienti.")
        return

    x = [d[0] for d in dati]
    y = [d[1] for d in dati]

    media_x = sum(x) / len(x)
    media_y = sum(y) / len(y)

    numeratore = sum(
        (a - media_x) * (b - media_y)
        for a, b in dati
    )

    denominatore_x = math.sqrt(
        sum((a - media_x) ** 2 for a in x)
    )

    denominatore_y = math.sqrt(
        sum((b - media_y) ** 2 for b in y)
    )

    if denominatore_x == 0 or denominatore_y == 0:
        correlazione = 0
    else:
        correlazione = numeratore / (
            denominatore_x * denominatore_y
        )

    print(f"\n{nome}")
    print(f"Partite disponibili: {len(dati)}")
    print(f"Correlazione con errore baseline: {correlazione:+.4f}")


analizza_variabile(
    "POSSESSO",
    [p["possesso_casa"] for p in partite],
    [p["possesso_ospite"] for p in partite],
)

analizza_variabile(
    "TIRI IN PORTA",
    [p["tiri_casa"] for p in partite],
    [p["tiri_ospite"] for p in partite],
)


print("\n===== FINE ANALISI =====")
print("Il baseline NON è stato modificato.")
