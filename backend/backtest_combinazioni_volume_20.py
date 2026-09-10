import csv
import math
from itertools import combinations

from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error


FEATURES = "data/serie_a_features.csv"
BASELINE = "data/serie_a_backtest_baseline.csv"


def numero(v):
    if v in ("", None):
        return None
    return float(v)


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
        raise RuntimeError(f"Feature non trovate: {chiave}")

    cp = numero(f["casa_tiri_in_porta_totale_pre"])
    cf = numero(f["casa_tiri_fuori_totale_pre"])
    op = numero(f["ospite_tiri_in_porta_totale_pre"])
    of = numero(f["ospite_tiri_fuori_totale_pre"])

    poss_c = numero(f["casa_possesso_totale_pre"])
    poss_o = numero(f["ospite_possesso_totale_pre"])

    xgf_c = numero(f["casa_xg_fatti_totale_pre"])
    xgf_o = numero(f["ospite_xg_fatti_totale_pre"])

    if None in (
        cp, cf, op, of,
        poss_c, poss_o,
        xgf_c, xgf_o
    ):
        continue

    tiri_c = cp + cf
    tiri_o = op + of

    if tiri_c > 0:
        precisione_c = cp / tiri_c
        xg_tiro_c = xgf_c / tiri_c
    else:
        precisione_c = 0.0
        xg_tiro_c = 0.0

    if tiri_o > 0:
        precisione_o = op / tiri_o
        xg_tiro_o = xgf_o / tiri_o
    else:
        precisione_o = 0.0
        xg_tiro_o = 0.0

    partite.append({
        "data": b["data"],
        "casa": b["casa"],
        "ospite": b["ospite"],

        "gol_casa": float(b["gol_casa_reali"]),
        "gol_ospite": float(b["gol_ospite_reali"]),

        "baseline_casa": float(b["gol_casa_attesi"]),
        "baseline_ospite": float(b["gol_ospite_attesi"]),

        "volume":
            tiri_c - tiri_o,

        "possesso":
            poss_c - poss_o,

        "tiri_porta":
            cp - op,

        "xg":
            xgf_c - xgf_o,

        "precisione":
            precisione_c - precisione_o,

        "xg_per_tiro":
            xg_tiro_c - xg_tiro_o,
    })


def valuta(predizioni):

    yc = [p["gol_casa"] for p in predizioni]
    yo = [p["gol_ospite"] for p in predizioni]

    pc = [p["pred_casa"] for p in predizioni]
    po = [p["pred_ospite"] for p in predizioni]

    mae_casa = mean_absolute_error(yc, pc)
    mae_ospite = mean_absolute_error(yo, po)

    rmse_casa = math.sqrt(
        mean_squared_error(yc, pc)
    )

    rmse_ospite = math.sqrt(
        mean_squared_error(yo, po)
    )

    return {
        "mae_casa": mae_casa,
        "mae_ospite": mae_ospite,
        "rmse_casa": rmse_casa,
        "rmse_ospite": rmse_ospite,
        "mae": (mae_casa + mae_ospite) / 2,
        "rmse": (rmse_casa + rmse_ospite) / 2,
    }


def test_variabili(nomi):

    valori = {
        nome: [
            p[nome]
            for p in partite
        ]
        for nome in nomi
    }

    predizioni = []

    for i, attuale in enumerate(partite):

        if i < 3:

            predizioni.append({
                "gol_casa": attuale["gol_casa"],
                "gol_ospite": attuale["gol_ospite"],
                "pred_casa": max(
                    0.0,
                    attuale["baseline_casa"]
                ),
                "pred_ospite": max(
                    0.0,
                    attuale["baseline_ospite"]
                ),
            })

            continue


        X_train = []
        yc_train = []
        yo_train = []

        for j in range(i):

            riga = [
                valori[nome][j]
                for nome in nomi
            ]

            if not all(math.isfinite(x) for x in riga):
                continue

            X_train.append(riga)

            yc_train.append(
                partite[j]["gol_casa"]
                - partite[j]["baseline_casa"]
            )

            yo_train.append(
                partite[j]["gol_ospite"]
                - partite[j]["baseline_ospite"]
            )


        if len(X_train) < 4:

            correzione_casa = 0.0
            correzione_ospite = 0.0

        else:

            modello_casa = LinearRegression()
            modello_ospite = LinearRegression()

            modello_casa.fit(X_train, yc_train)
            modello_ospite.fit(X_train, yo_train)

            x_test = [[
                valori[nome][i]
                for nome in nomi
            ]]

            correzione_casa = float(
                modello_casa.predict(x_test)[0]
            )

            correzione_ospite = float(
                modello_ospite.predict(x_test)[0]
            )


        predizioni.append({
            "gol_casa": attuale["gol_casa"],
            "gol_ospite": attuale["gol_ospite"],

            "pred_casa": max(
                0.0,
                attuale["baseline_casa"]
                + correzione_casa
            ),

            "pred_ospite": max(
                0.0,
                attuale["baseline_ospite"]
                + correzione_ospite
            ),
        })


    return valuta(predizioni)


# ============================================================
# BASELINE
# ============================================================

baseline_pred = []

for p in partite:

    baseline_pred.append({
        "gol_casa": p["gol_casa"],
        "gol_ospite": p["gol_ospite"],
        "pred_casa": max(0.0, p["baseline_casa"]),
        "pred_ospite": max(0.0, p["baseline_ospite"]),
    })


base = valuta(baseline_pred)


# ============================================================
# TEST
# ============================================================

variabili = [
    "volume",
    "possesso",
    "tiri_porta",
    "xg",
    "precisione",
    "xg_per_tiro",
]


risultati = []


# Tutte le combinazioni da 1 a 4 variabili.
for dimensione in range(1, 5):

    for combinazione in combinations(
        variabili,
        dimensione
    ):

        # Il volume è il candidato principale.
        # Per le combinazioni di dimensione > 1
        # lo includiamo sempre.
        if "volume" not in combinazione:
            continue

        risultato = test_variabili(combinazione)

        risultati.append({
            "variabili": "+".join(combinazione),
            **risultato
        })


risultati.sort(
    key=lambda r: (r["mae"], r["rmse"])
)


print()
print("======================================================")
print(" TEST COMBINAZIONI VOLUME TIRI - WALK-FORWARD")
print("======================================================")
print(f"Partite utilizzate: {len(partite)}")
print()
print(
    f"{'Variabili':38s}"
    f" MAE      RMSE     dMAE      dRMSE"
)
print("-" * 82)


print(
    f"{'BASELINE':38s}"
    f" {base['mae']:.4f}"
    f"   {base['rmse']:.4f}"
    f"   +0.0000"
    f"   +0.0000"
)


for r in risultati:

    print(
        f"{r['variabili']:38s}"
        f" {r['mae']:.4f}"
        f"   {r['rmse']:.4f}"
        f"   {r['mae'] - base['mae']:+.4f}"
        f"   {r['rmse'] - base['rmse']:+.4f}"
    )


print()
print("======================================================")
print(" MIGLIORI CANDIDATI")
print("======================================================")

migliori = [
    r for r in risultati
    if r["mae"] < base["mae"]
    and r["rmse"] < base["rmse"]
]

migliori.sort(
    key=lambda r: (r["mae"], r["rmse"])
)

if migliori:

    for r in migliori[:10]:

        print(
            f"{r['variabili']:38s}"
            f" MAE={r['mae']:.4f}"
            f" RMSE={r['rmse']:.4f}"
        )

else:

    print("Nessuna combinazione migliora entrambi gli indicatori.")


print()
print("======================================================")
print(" RIFERIMENTI")
print("======================================================")
print("Baseline ufficiale: MAE=0.7683 RMSE=0.9473")
print("Volume tiri:        MAE=0.7547 RMSE=0.9261")
print()
print("Nessuna modifica al modello principale.")
