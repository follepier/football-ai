import csv
import math
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error

DATASET = "../data/serie_a_features.csv"
BASELINE = "../data/serie_a_backtest_baseline.csv"


def num(x):
    return float(x) if x not in ("", None) else 0.0


def ratio(a, b):
    return a / b if b > 0 else 0.0


# --------------------------------------------------
# CARICAMENTO
# --------------------------------------------------

with open(DATASET, encoding="utf-8") as f:
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

    casa_xg = num(r["casa_xg_fatti_totale_pre"])
    ospite_xg = num(r["ospite_xg_fatti_totale_pre"])

    casa_tipi = num(r["casa_tiri_in_porta_totale_pre"])
    casa_tifu = num(r["casa_tiri_fuori_totale_pre"])

    ospite_tipi = num(r["ospite_tiri_in_porta_totale_pre"])
    ospite_tifu = num(r["ospite_tiri_fuori_totale_pre"])

    casa_tiri = casa_tipi + casa_tifu
    ospite_tiri = ospite_tipi + ospite_tifu

    indice[chiave] = {

        # 1. xG
        "xg":
            casa_xg - ospite_xg,

        # 2. VOLUME TIRI
        "volume_tiri":
            casa_tiri - ospite_tiri,

        # 3. TIRI IN PORTA
        "tiri_in_porta":
            casa_tipi - ospite_tipi,

        # 4. PRECISIONE
        "precisione":
            ratio(casa_tipi, casa_tiri)
            -
            ratio(ospite_tipi, ospite_tiri),

        # 5. QUALITA' MEDIA DEL TIRO
        "xg_per_tiro":
            ratio(casa_xg, casa_tiri)
            -
            ratio(ospite_xg, ospite_tiri),
    }


# --------------------------------------------------
# PREPARAZIONE DELLE 20 PARTITE
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
# FUNZIONE TEST
# --------------------------------------------------

def esegui_test(nome):

    X = [
        [p[nome]]
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
        "variabile": nome,
        "mae":
            (mae_casa + mae_ospite) / 2,
        "rmse":
            (rmse_casa + rmse_ospite) / 2,
    }


# --------------------------------------------------
# TEST
# --------------------------------------------------

variabili = [
    "xg",
    "volume_tiri",
    "tiri_in_porta",
    "precisione",
    "xg_per_tiro",
]

risultati = []

for v in variabili:
    risultati.append(
        esegui_test(v)
    )


# --------------------------------------------------
# RISULTATI
# --------------------------------------------------

print()
print("===== TEST SINGOLE VARIABILI TIRO =====")
print("Partite utilizzate: 20")
print()

print(
    f"{'Variabile':<20}"
    f"{'MAE':>10}"
    f"{'RMSE':>10}"
    f"{'Δ MAE':>12}"
    f"{'Δ RMSE':>12}"
)

print("-" * 64)

for r in risultati:

    delta_mae = r["mae"] - 0.7683
    delta_rmse = r["rmse"] - 0.9473

    print(
        f"{r['variabile']:<20}"
        f"{r['mae']:>10.4f}"
        f"{r['rmse']:>10.4f}"
        f"{delta_mae:>+12.4f}"
        f"{delta_rmse:>+12.4f}"
    )

print()
print("BASELINE")
print("MAE  = 0.7683")
print("RMSE = 0.9473")
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
    migliore_mae["variabile"],
    f"({migliore_mae['mae']:.4f})"
)

print(
    "Migliore RMSE:",
    migliore_rmse["variabile"],
    f"({migliore_rmse['rmse']:.4f})"
)
