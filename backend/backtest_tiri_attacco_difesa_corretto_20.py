import csv
import math
from pathlib import Path

from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error

FEATURES = Path("data/serie_a_features.csv")
BASELINE = Path("data/serie_a_backtest_baseline.csv")
OUTPUT = Path("data/serie_a_tiri_attacco_difesa_corretto_20.csv")


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


# ============================================================
# CARICAMENTO
# ============================================================

with FEATURES.open(newline="", encoding="utf-8") as f:
    features = list(csv.DictReader(f))

with BASELINE.open(newline="", encoding="utf-8") as f:
    baseline = list(csv.DictReader(f))


# ============================================================
# FEATURE PRE-PARTITA
# ============================================================

indice = {}

for r in features:

    # TIRI TOTALI PRE-PARTITA
    casa_tiri = (
        num(r["casa_tiri_in_porta_totale_pre"])
        + num(r["casa_tiri_fuori_totale_pre"])
    )

    ospite_tiri = (
        num(r["ospite_tiri_in_porta_totale_pre"])
        + num(r["ospite_tiri_fuori_totale_pre"])
    )

    # TIRI IN PORTA PRE-PARTITA
    casa_porta = num(
        r["casa_tiri_in_porta_totale_pre"]
    )

    ospite_porta = num(
        r["ospite_tiri_in_porta_totale_pre"]
    )

    indice[chiave(r)] = {
        "casa_tiri": casa_tiri,
        "ospite_tiri": ospite_tiri,
        "casa_porta": casa_porta,
        "ospite_porta": ospite_porta,
    }


# ============================================================
# MATCH
# ============================================================

rows = []

for r in baseline:

    k = chiave(r)

    if k not in indice:
        raise SystemExit(
            f"Feature mancante: {k}"
        )

    f = indice[k]

    # --------------------------------------------------------
    # CASA
    #
    # Attacco casa:
    #   quanti tiri produce la casa
    #
    # Difesa avversaria:
    #   quanti tiri concede l'ospite
    #
    # --------------------------------------------------------

    attacco_casa = f["casa_tiri"]
    concessi_ospite = f["ospite_tiri"]

    # --------------------------------------------------------
    # OSPITE
    #
    # Attacco ospite:
    #   quanti tiri produce l'ospite
    #
    # Difesa avversaria:
    #   quanti tiri concede la casa
    #
    # --------------------------------------------------------

    attacco_ospite = f["ospite_tiri"]
    concessi_casa = f["casa_tiri"]

    # --------------------------------------------------------
    # DIFFERENZA ATTACCO/DIFESA
    #
    # Per casa:
    # produzione casa - produzione ospite
    #
    # Per ospite:
    # produzione ospite - produzione casa
    #
    # --------------------------------------------------------

    indice_forza_casa = (
        attacco_casa - concessi_ospite
    )

    indice_forza_ospite = (
        attacco_ospite - concessi_casa
    )

    # --------------------------------------------------------
    # MEDIA ATTACCO/DIFESA AVVERSARIA
    #
    # Questa volta la struttura è esplicita:
    #
    # casa:
    #   attacco casa + tiri concessi ospite
    #
    # ospite:
    #   attacco ospite + tiri concessi casa
    #
    # --------------------------------------------------------

    tiri_target_casa = (
        attacco_casa + concessi_ospite
    ) / 2.0

    tiri_target_ospite = (
        attacco_ospite + concessi_casa
    ) / 2.0

    # --------------------------------------------------------
    # TIRI IN PORTA
    # --------------------------------------------------------

    porta_casa = f["casa_porta"]
    porta_ospite = f["ospite_porta"]

    # Differenza tiri in porta
    diff_porta_casa = (
        porta_casa - porta_ospite
    )

    diff_porta_ospite = (
        porta_ospite - porta_casa
    )

    rows.append({
        "data": r["data"],
        "casa": r["casa"],
        "ospite": r["ospite"],
        "gol_casa": num(r["gol_casa_reali"]),
        "gol_ospite": num(r["gol_ospite_reali"]),
        "base_casa": num(r["gol_casa_attesi"]),
        "base_ospite": num(r["gol_ospite_attesi"]),

        "attacco_casa": attacco_casa,
        "attacco_ospite": attacco_ospite,

        "concessi_casa": concessi_casa,
        "concessi_ospite": concessi_ospite,

        "indice_forza_casa": indice_forza_casa,
        "indice_forza_ospite": indice_forza_ospite,

        "target_casa": tiri_target_casa,
        "target_ospite": tiri_target_ospite,

        "porta_casa": porta_casa,
        "porta_ospite": porta_ospite,

        "diff_porta_casa": diff_porta_casa,
        "diff_porta_ospite": diff_porta_ospite,
    })


# ============================================================
# DATI REALI
# ============================================================

y_casa = [r["gol_casa"] for r in rows]
y_ospite = [r["gol_ospite"] for r in rows]

base_casa = [r["base_casa"] for r in rows]
base_ospite = [r["base_ospite"] for r in rows]


# ============================================================
# METRICHE
# ============================================================

def metriche(ph, po):

    mae_c = mean_absolute_error(
        y_casa, ph
    )

    mae_o = mean_absolute_error(
        y_ospite, po
    )

    rmse_c = math.sqrt(
        mean_squared_error(y_casa, ph)
    )

    rmse_o = math.sqrt(
        mean_squared_error(y_ospite, po)
    )

    return {
        "mae_casa": mae_c,
        "mae_ospite": mae_o,
        "mae": (mae_c + mae_o) / 2.0,
        "rmse_casa": rmse_c,
        "rmse_ospite": rmse_o,
        "rmse": (rmse_c + rmse_o) / 2.0,
    }


baseline_metriche = metriche(
    base_casa,
    base_ospite
)


# ============================================================
# WALK-FORWARD GENERICO
# ============================================================

def test_variabile(
    valori_casa,
    valori_ospite,
    nome
):

    pred_casa = []
    pred_ospite = []

    for i in range(len(rows)):

        # Prime 3 partite:
        # nessuna correzione.
        if i < 3:

            pred_casa.append(
                base_casa[i]
            )

            pred_ospite.append(
                base_ospite[i]
            )

            continue

        # ----------------------------------------------------
        # SOLO PARTITE PRECEDENTI
        # ----------------------------------------------------

        X_train_casa = [
            [valori_casa[j]]
            for j in range(i)
        ]

        X_train_ospite = [
            [valori_ospite[j]]
            for j in range(i)
        ]

        residui_casa = [
            y_casa[j] - base_casa[j]
            for j in range(i)
        ]

        residui_ospite = [
            y_ospite[j] - base_ospite[j]
            for j in range(i)
        ]

        modello_casa = LinearRegression()
        modello_ospite = LinearRegression()

        modello_casa.fit(
            X_train_casa,
            residui_casa
        )

        modello_ospite.fit(
            X_train_ospite,
            residui_ospite
        )

        correzione_casa = float(
            modello_casa.predict(
                [[valori_casa[i]]]
            )[0]
        )

        correzione_ospite = float(
            modello_ospite.predict(
                [[valori_ospite[i]]]
            )[0]
        )

        pred_casa.append(
            base_casa[i] + correzione_casa
        )

        pred_ospite.append(
            base_ospite[i] + correzione_ospite
        )

    return (
        metriche(pred_casa, pred_ospite),
        pred_casa,
        pred_ospite
    )


# ============================================================
# TEST
# ============================================================

test = {}

test["indice_forza_tiri"] = test_variabile(
    [r["indice_forza_casa"] for r in rows],
    [r["indice_forza_ospite"] for r in rows],
    "indice_forza_tiri"
)

test["target_attacco_difesa"] = test_variabile(
    [r["target_casa"] for r in rows],
    [r["target_ospite"] for r in rows],
    "target_attacco_difesa"
)

test["tiri_concessi"] = test_variabile(
    [r["concessi_casa"] for r in rows],
    [r["concessi_ospite"] for r in rows],
    "tiri_concessi"
)

test["differenza_porta"] = test_variabile(
    [r["diff_porta_casa"] for r in rows],
    [r["diff_porta_ospite"] for r in rows],
    "differenza_porta"
)


# ============================================================
# STAMPA RISULTATI
# ============================================================

print("=" * 82)
print("TEST TIRI ATTACCO/DIFESA - WALK-FORWARD CORRETTO")
print("=" * 82)

print()
print("BASELINE")
print(
    f"MAE  = {baseline_metriche['mae']:.4f}"
)
print(
    f"RMSE = {baseline_metriche['rmse']:.4f}"
)

print()
print("-" * 82)
print(
    f"{'VARIABILE':30s}"
    f"{'MAE':>12s}"
    f"{'RMSE':>12s}"
    f"{'DELTA MAE':>14s}"
    f"{'DELTA RMSE':>15s}"
)
print("-" * 82)

for nome, (m, _, _) in test.items():

    d_mae = (
        m["mae"]
        - baseline_metriche["mae"]
    )

    d_rmse = (
        m["rmse"]
        - baseline_metriche["rmse"]
    )

    print(
        f"{nome:30s}"
        f"{m['mae']:12.4f}"
        f"{m['rmse']:12.4f}"
        f"{d_mae:+14.4f}"
        f"{d_rmse:+15.4f}"
    )

print("-" * 82)

print()
print("CRITERIO:")
print("Delta negativo = miglioramento")
print("Delta positivo = peggioramento")

print()
print("=" * 82)
print("VARIABILI CHE MIGLIORANO ENTRAMBI")
print("=" * 82)

migliori = []

for nome, (m, _, _) in test.items():

    d_mae = (
        m["mae"]
        - baseline_metriche["mae"]
    )

    d_rmse = (
        m["rmse"]
        - baseline_metriche["rmse"]
    )

    if d_mae < 0 and d_rmse < 0:

        migliori.append(
            (nome, d_mae, d_rmse)
        )

        print(
            f"{nome}: "
            f"MAE {d_mae:+.4f} | "
            f"RMSE {d_rmse:+.4f}"
        )

if not migliori:
    print("Nessuna variabile migliora contemporaneamente MAE e RMSE.")

print()
print("=" * 82)
print("CONTROLLO STABILITA' PREDIZIONI")
print("=" * 82)

for nome, (m, ph, po) in test.items():

    minimo_casa = min(ph)
    minimo_ospite = min(po)

    massimo_casa = max(ph)
    massimo_ospite = max(po)

    print()
    print(nome)
    print(
        f"Casa   min={minimo_casa:.3f} "
        f"max={massimo_casa:.3f}"
    )
    print(
        f"Ospite min={minimo_ospite:.3f} "
        f"max={massimo_ospite:.3f}"
    )


# ============================================================
# SALVATAGGIO
# ============================================================

with OUTPUT.open(
    "w",
    newline="",
    encoding="utf-8"
) as f:

    writer = csv.writer(f)

    writer.writerow([
        "variabile",
        "mae",
        "rmse",
        "delta_mae",
        "delta_rmse",
    ])

    for nome, (m, _, _) in test.items():

        writer.writerow([
            nome,
            m["mae"],
            m["rmse"],
            m["mae"] - baseline_metriche["mae"],
            m["rmse"] - baseline_metriche["rmse"],
        ])

print()
print(f"File salvato: {OUTPUT}")
print("baseline.py NON modificato.")
print("Dataset principali NON modificati.")
