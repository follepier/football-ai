import csv
import math
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error

FEATURES = "../data/serie_a_features.csv"
BASELINE = "../data/serie_a_backtest_baseline.csv"


def num(x):
    return float(x) if x not in ("", None) else 0.0


# --------------------------------------------------
# CARICAMENTO
# --------------------------------------------------

with open(FEATURES, encoding="utf-8") as f:
    features = list(csv.DictReader(f))

with open(BASELINE, encoding="utf-8") as f:
    baseline = list(csv.DictReader(f))


# --------------------------------------------------
# INDICE FEATURE PRE-PARTITA
# --------------------------------------------------

indice = {}

for r in features:

    chiave = (
        r["data"],
        r["casa"],
        r["ospite"]
    )

    casa_tiri_porta = num(
        r["casa_tiri_in_porta_totale_pre"]
    )

    casa_tiri_fuori = num(
        r["casa_tiri_fuori_totale_pre"]
    )

    ospite_tiri_porta = num(
        r["ospite_tiri_in_porta_totale_pre"]
    )

    ospite_tiri_fuori = num(
        r["ospite_tiri_fuori_totale_pre"]
    )

    casa_tiri_totali = (
        casa_tiri_porta + casa_tiri_fuori
    )

    ospite_tiri_totali = (
        ospite_tiri_porta + ospite_tiri_fuori
    )

    # DIFFERENZE CASA - OSPITE
    volume_tiri = (
        casa_tiri_totali
        - ospite_tiri_totali
    )

    tiri_in_porta = (
        casa_tiri_porta
        - ospite_tiri_porta
    )

    possesso = (
        num(r["casa_possesso_totale_pre"])
        - num(r["ospite_possesso_totale_pre"])
    )

    indice[chiave] = {
        "volume_tiri": volume_tiri,
        "tiri_in_porta": tiri_in_porta,
        "possesso": possesso,
    }


# --------------------------------------------------
# PREPARAZIONE PARTITE
# --------------------------------------------------

partite = []

for b in baseline:

    chiave = (
        b["data"],
        b["casa"],
        b["ospite"]
    )

    f = indice.get(chiave)

    if f is None:
        raise RuntimeError(
            f"Feature non trovate: {chiave}"
        )

    partite.append({
        "data": b["data"],
        "casa": b["casa"],
        "ospite": b["ospite"],

        "gol_casa":
            float(b["gol_casa_reali"]),

        "gol_ospite":
            float(b["gol_ospite_reali"]),

        "baseline_casa":
            float(b["gol_casa_attesi"]),

        "baseline_ospite":
            float(b["gol_ospite_attesi"]),

        **f
    })


# --------------------------------------------------
# TEST COMBINAZIONE
# --------------------------------------------------

def esegui_test(nome, variabili):

    X = [
        [p[v] for v in variabili]
        for p in partite
    ]

    y_casa = [
        p["gol_casa"] - p["baseline_casa"]
        for p in partite
    ]

    y_ospite = [
        p["gol_ospite"] - p["baseline_ospite"]
        for p in partite
    ]

    pred_casa = []
    pred_ospite = []

    for i in range(len(partite)):

        X_train = X[:i] + X[i + 1:]

        yc_train = y_casa[:i] + y_casa[i + 1:]
        yo_train = y_ospite[:i] + y_ospite[i + 1:]

        modello_casa = LinearRegression()
        modello_ospite = LinearRegression()

        modello_casa.fit(
            X_train,
            yc_train
        )

        modello_ospite.fit(
            X_train,
            yo_train
        )

        correzione_casa = float(
            modello_casa.predict([X[i]])[0]
        )

        correzione_ospite = float(
            modello_ospite.predict([X[i]])[0]
        )

        pred_casa.append(
            partite[i]["baseline_casa"]
            + correzione_casa
        )

        pred_ospite.append(
            partite[i]["baseline_ospite"]
            + correzione_ospite
        )

    reali_casa = [
        p["gol_casa"]
        for p in partite
    ]

    reali_ospite = [
        p["gol_ospite"]
        for p in partite
    ]

    mae_casa = mean_absolute_error(
        reali_casa,
        pred_casa
    )

    mae_ospite = mean_absolute_error(
        reali_ospite,
        pred_ospite
    )

    rmse_casa = math.sqrt(
        mean_squared_error(
            reali_casa,
            pred_casa
        )
    )

    rmse_ospite = math.sqrt(
        mean_squared_error(
            reali_ospite,
            pred_ospite
        )
    )

    return {
        "nome": nome,
        "mae": (mae_casa + mae_ospite) / 2,
        "rmse": (rmse_casa + rmse_ospite) / 2,
    }


# --------------------------------------------------
# COMBINAZIONI
# --------------------------------------------------

test = [

    (
        "Volume tiri",
        ["volume_tiri"]
    ),

    (
        "Possesso",
        ["possesso"]
    ),

    (
        "Volume + possesso",
        [
            "volume_tiri",
            "possesso"
        ]
    ),

    (
        "Volume + tiri in porta",
        [
            "volume_tiri",
            "tiri_in_porta"
        ]
    ),

    (
        "Volume + possesso + tiri in porta",
        [
            "volume_tiri",
            "possesso",
            "tiri_in_porta"
        ]
    ),
]


risultati = []

for nome, variabili in test:

    risultati.append(
        esegui_test(
            nome,
            variabili
        )
    )


# --------------------------------------------------
# RISULTATI
# --------------------------------------------------

print()
print("===== COMBINAZIONI VARIABILI =====")
print("Partite utilizzate: 20")
print()

print(
    f"{'Modello':<38}"
    f"{'MAE':>10}"
    f"{'RMSE':>10}"
    f"{'Δ MAE':>12}"
    f"{'Δ RMSE':>12}"
)

print("-" * 82)

print(
    f"{'BASELINE':<38}"
    f"{0.7683:>10.4f}"
    f"{0.9473:>10.4f}"
    f"{0.0000:>+12.4f}"
    f"{0.0000:>+12.4f}"
)

for r in risultati:

    delta_mae = r["mae"] - 0.7683
    delta_rmse = r["rmse"] - 0.9473

    print(
        f"{r['nome']:<38}"
        f"{r['mae']:>10.4f}"
        f"{r['rmse']:>10.4f}"
        f"{delta_mae:>+12.4f}"
        f"{delta_rmse:>+12.4f}"
    )

print()

migliore_mae = min(
    risultati,
    key=lambda x: x["mae"]
)

migliore_rmse = min(
    risultati,
    key=lambda x: x["rmse"]
)

print(
    "Migliore MAE:",
    migliore_mae["nome"],
    f"({migliore_mae['mae']:.4f})"
)

print(
    "Migliore RMSE:",
    migliore_rmse["nome"],
    f"({migliore_rmse['rmse']:.4f})"
)
