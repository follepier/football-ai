import csv
import math
from pathlib import Path

from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error

FEATURES = Path("data/serie_a_features.csv")
BASELINE = Path("data/serie_a_backtest_baseline.csv")
OUTPUT = Path("data/serie_a_tiri_attacco_difesa_walkforward_20.csv")


def num(x):
    if x is None or x == "":
        return 0.0
    return float(x)


def chiave(r):
    return (
        r["data"].strip(),
        r["casa"].strip(),
        r["ospite"].strip(),
    )


with FEATURES.open(newline="", encoding="utf-8") as f:
    features = list(csv.DictReader(f))

with BASELINE.open(newline="", encoding="utf-8") as f:
    baseline = list(csv.DictReader(f))


# ============================================================
# COSTRUZIONE DELLE VARIABILI
# ============================================================

indice = {}

for r in features:

    # TIRI TOTALI
    casa_tiri = (
        num(r["casa_tiri_in_porta_totale_pre"])
        + num(r["casa_tiri_fuori_totale_pre"])
    )

    ospite_tiri = (
        num(r["ospite_tiri_in_porta_totale_pre"])
        + num(r["ospite_tiri_fuori_totale_pre"])
    )

    # TIRI IN PORTA
    casa_porta = num(
        r["casa_tiri_in_porta_totale_pre"]
    )

    ospite_porta = num(
        r["ospite_tiri_in_porta_totale_pre"]
    )

    # TIRI FUORI
    casa_fuori = num(
        r["casa_tiri_fuori_totale_pre"]
    )

    ospite_fuori = num(
        r["ospite_tiri_fuori_totale_pre"]
    )

    indice[chiave(r)] = {

        # 1. Volume offensivo puro
        "tiri_effettuati_casa": casa_tiri,
        "tiri_effettuati_ospite": ospite_tiri,

        # 2. Volume concesso
        # Per la squadra di casa, i tiri concessi
        # sono quelli prodotti dall'ospite.
        "tiri_concessi_casa": ospite_tiri,
        "tiri_concessi_ospite": casa_tiri,

        # 3. Tiri in porta
        "porta_casa": casa_porta,
        "porta_ospite": ospite_porta,

        # 4. Tiri fuori
        "fuori_casa": casa_fuori,
        "fuori_ospite": ospite_fuori,
    }


# ============================================================
# MATCH DEL BENCHMARK
# ============================================================

rows = []

for r in baseline:

    k = chiave(r)

    if k not in indice:
        raise SystemExit(f"Feature mancante: {k}")

    f = indice[k]

    # --------------------------------------------------------
    # Variabili squadra casa
    # --------------------------------------------------------

    att_casa = f["tiri_effettuati_casa"]
    dif_casa = f["tiri_concessi_casa"]

    # --------------------------------------------------------
    # Variabili squadra ospite
    # --------------------------------------------------------

    att_ospite = f["tiri_effettuati_ospite"]
    dif_ospite = f["tiri_concessi_ospite"]

    # --------------------------------------------------------
    # "TIRI ATTESI" basati su attacco + difesa avversaria
    #
    # Media semplice:
    # 50% produzione propria
    # 50% concessione avversaria
    #
    # NON è un peso arbitrario nel modello:
    # serve soltanto come trasformazione simmetrica
    # da testare.
    # --------------------------------------------------------

    tiri_attesi_casa = (
        att_casa + dif_ospite
    ) / 2

    tiri_attesi_ospite = (
        att_ospite + dif_casa
    ) / 2

    # --------------------------------------------------------
    # Stessa trasformazione per i tiri in porta
    # --------------------------------------------------------

    porta_casa = f["porta_casa"]
    porta_ospite = f["porta_ospite"]

    porta_attesa_casa = (
        porta_casa + porta_ospite
    ) / 2

    porta_attesa_ospite = (
        porta_ospite + porta_casa
    ) / 2

    rows.append({
        "data": r["data"],
        "casa": r["casa"],
        "ospite": r["ospite"],
        "gol_casa": num(r["gol_casa_reali"]),
        "gol_ospite": num(r["gol_ospite_reali"]),
        "base_casa": num(r["gol_casa_attesi"]),
        "base_ospite": num(r["gol_ospite_attesi"]),

        "att_casa": att_casa,
        "att_ospite": att_ospite,

        "dif_casa": dif_casa,
        "dif_ospite": dif_ospite,

        "tiri_attesi_casa": tiri_attesi_casa,
        "tiri_attesi_ospite": tiri_attesi_ospite,

        "porta_casa": porta_casa,
        "porta_ospite": porta_ospite,

        "porta_attesa_casa": porta_attesa_casa,
        "porta_attesa_ospite": porta_attesa_ospite,
    })


# ============================================================
# FUNZIONI METRICHE
# ============================================================

reali_casa = [r["gol_casa"] for r in rows]
reali_ospite = [r["gol_ospite"] for r in rows]

base_casa = [r["base_casa"] for r in rows]
base_ospite = [r["base_ospite"] for r in rows]


def metriche(ph, po):

    mae_c = mean_absolute_error(
        reali_casa, ph
    )

    mae_o = mean_absolute_error(
        reali_ospite, po
    )

    rmse_c = math.sqrt(
        mean_squared_error(reali_casa, ph)
    )

    rmse_o = math.sqrt(
        mean_squared_error(reali_ospite, po)
    )

    return {
        "mae_casa": mae_c,
        "mae_ospite": mae_o,
        "mae": (mae_c + mae_o) / 2,
        "rmse_casa": rmse_c,
        "rmse_ospite": rmse_o,
        "rmse": (rmse_c + rmse_o) / 2,
    }


m_base = metriche(
    base_casa,
    base_ospite
)


# ============================================================
# TEST DI UNA SINGOLA VARIABILE
# ============================================================

def test_variabile(nome, valori_casa, valori_ospite):

    pred_casa = []
    pred_ospite = []

    for i in range(len(rows)):

        # Per le prime 3 partite non abbiamo abbastanza
        # storico per stimare una relazione.
        if i < 3:
            pred_casa.append(base_casa[i])
            pred_ospite.append(base_ospite[i])
            continue

        X_train = [
            [valori_casa[j]]
            for j in range(i)
        ]

        # Il modello impara la correzione della baseline.
        residui_casa = [
            reali_casa[j] - base_casa[j]
            for j in range(i)
        ]

        residui_ospite = [
            reali_ospite[j] - base_ospite[j]
            for j in range(i)
        ]

        modello_casa = LinearRegression()
        modello_ospite = LinearRegression()

        modello_casa.fit(
            X_train,
            residui_casa
        )

        modello_ospite.fit(
            X_train,
            residui_ospite
        )

        x_test_casa = [[valori_casa[i]]]
        x_test_ospite = [[valori_ospite[i]]]

        correzione_casa = float(
            modello_casa.predict(
                x_test_casa
            )[0]
        )

        correzione_ospite = float(
            modello_ospite.predict(
                x_test_ospite
            )[0]
        )

        pred_casa.append(
            base_casa[i] + correzione_casa
        )

        pred_ospite.append(
            base_ospite[i] + correzione_ospite
        )

    return metriche(
        pred_casa,
        pred_ospite
    ), pred_casa, pred_ospite


# ============================================================
# TEST VARIABILI
# ============================================================

risultati = {}

# A) Tiri effettuati
risultati["tiri_effettuati"] = test_variabile(
    "tiri_effettuati",
    [r["att_casa"] for r in rows],
    [r["att_ospite"] for r in rows],
)

# B) Tiri concessi
risultati["tiri_concessi"] = test_variabile(
    "tiri_concessi",
    [r["dif_casa"] for r in rows],
    [r["dif_ospite"] for r in rows],
)

# C) Tiri attesi attacco + difesa
risultati["tiri_attesi"] = test_variabile(
    "tiri_attesi",
    [r["tiri_attesi_casa"] for r in rows],
    [r["tiri_attesi_ospite"] for r in rows],
)

# D) Tiri in porta
risultati["tiri_in_porta"] = test_variabile(
    "tiri_in_porta",
    [r["porta_casa"] for r in rows],
    [r["porta_ospite"] for r in rows],
)

# E) Tiri in porta attesi
risultati["tiri_in_porta_attesi"] = test_variabile(
    "tiri_in_porta_attesi",
    [r["porta_attesa_casa"] for r in rows],
    [r["porta_attesa_ospite"] for r in rows],
)


# ============================================================
# STAMPA
# ============================================================

print("=" * 78)
print("TEST TIRI - ATTACCO / DIFESA - WALK-FORWARD")
print("=" * 78)

print()
print("BASELINE")
print(
    f"MAE  = {m_base['mae']:.4f}"
)
print(
    f"RMSE = {m_base['rmse']:.4f}"
)

print()
print("-" * 78)
print(
    f"{'VARIABILE':30s}"
    f"{'MAE':>12s}"
    f"{'RMSE':>12s}"
    f"{'DELTA MAE':>14s}"
    f"{'DELTA RMSE':>15s}"
)
print("-" * 78)

for nome, (m, _, _) in risultati.items():

    d_mae = m["mae"] - m_base["mae"]
    d_rmse = m["rmse"] - m_base["rmse"]

    print(
        f"{nome:30s}"
        f"{m['mae']:12.4f}"
        f"{m['rmse']:12.4f}"
        f"{d_mae:+14.4f}"
        f"{d_rmse:+15.4f}"
    )

print("-" * 78)

print()
print("CRITERIO:")
print("Delta negativo = miglioramento")
print("Delta positivo = peggioramento")

print()
print("=" * 78)
print("DETTAGLIO MIGLIORAMENTO")
print("=" * 78)

for nome, (m, _, _) in risultati.items():

    d_mae = m["mae"] - m_base["mae"]
    d_rmse = m["rmse"] - m_base["rmse"]

    if d_mae < 0 and d_rmse < 0:
        stato = ">>> MIGLIORA MAE E RMSE <<<"
    elif d_mae < 0:
        stato = ">>> MIGLIORA SOLO MAE <<<"
    elif d_rmse < 0:
        stato = ">>> MIGLIORA SOLO RMSE <<<"
    else:
        stato = "nessun miglioramento"

    print(
        f"{nome}: {stato}"
    )


# ============================================================
# SALVATAGGIO
# ============================================================

with OUTPUT.open("w", newline="", encoding="utf-8") as f:

    writer = csv.writer(f)

    writer.writerow([
        "variabile",
        "mae",
        "rmse",
        "delta_mae",
        "delta_rmse",
    ])

    for nome, (m, _, _) in risultati.items():

        writer.writerow([
            nome,
            m["mae"],
            m["rmse"],
            m["mae"] - m_base["mae"],
            m["rmse"] - m_base["rmse"],
        ])

print()
print(f"File salvato: {OUTPUT}")
print("baseline.py NON modificato.")
print("dataset principali NON modificati.")
