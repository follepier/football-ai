import csv
import math
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

    if None in (cp, cf, op, of):
        raise RuntimeError(f"Tiri mancanti: {chiave}")

    tiri_casa = cp + cf
    tiri_ospite = op + of

    partite.append({
        "data": b["data"],
        "casa": b["casa"],
        "ospite": b["ospite"],
        "gol_casa": float(b["gol_casa_reali"]),
        "gol_ospite": float(b["gol_ospite_reali"]),
        "baseline_casa": float(b["gol_casa_attesi"]),
        "baseline_ospite": float(b["gol_ospite_attesi"]),
        "tiri_casa": tiri_casa,
        "tiri_ospite": tiri_ospite,
    })


def costruisci_variabile(p, nome):

    tc = p["tiri_casa"]
    to = p["tiri_ospite"]

    if nome == "tiri_prodotti_diff":
        return tc - to

    if nome == "tiri_concessi_diff":
        # Tiri concessi dalla squadra di casa =
        # tiri prodotti dall'ospite e viceversa.
        concessi_casa = to
        concessi_ospite = tc
        return concessi_casa - concessi_ospite

    if nome == "indice_attacco_difesa":
        # Per la squadra di casa:
        # propri tiri / tiri concessi all'avversario
        #
        # Per l'ospite:
        # propri tiri / tiri concessi all'avversario
        #
        # Usiamo il logaritmo del rapporto per
        # evitare scale eccessivamente sbilanciate.
        eps = 0.1

        indice_casa = math.log(
            (tc + eps) / (to + eps)
        )

        indice_ospite = math.log(
            (to + eps) / (tc + eps)
        )

        return indice_casa - indice_ospite

    if nome == "tiri_somma_diff":
        # Intensità complessiva della partita.
        return (tc + to)

    raise ValueError(nome)


variabili = [
    "tiri_prodotti_diff",
    "tiri_concessi_diff",
    "indice_attacco_difesa",
    "tiri_somma_diff",
]


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

    return (
        (mae_casa + mae_ospite) / 2,
        (rmse_casa + rmse_ospite) / 2
    )


# ============================================================
# BASELINE
# ============================================================

baseline_pred = []

for p in partite:
    baseline_pred.append({
        **p,
        "pred_casa": max(0.0, p["baseline_casa"]),
        "pred_ospite": max(0.0, p["baseline_ospite"]),
    })

mae_base, rmse_base = valuta(baseline_pred)


print()
print("==============================================")
print(" VOLUME TIRI - ATTACCO / DIFESA")
print(" WALK-FORWARD")
print("==============================================")
print(f"Partite utilizzate: {len(partite)}")
print()


# ============================================================
# TEST
# ============================================================

for nome in variabili:

    valori = [
        costruisci_variabile(p, nome)
        for p in partite
    ]

    predizioni = []

    for i, attuale in enumerate(partite):

        # Prime 3 partite: nessun addestramento.
        if i < 3:

            predizioni.append({
                **attuale,
                "pred_casa":
                    max(0.0, attuale["baseline_casa"]),
                "pred_ospite":
                    max(0.0, attuale["baseline_ospite"]),
            })

            continue


        X_train = [
            [valori[j]]
            for j in range(i)
            if math.isfinite(valori[j])
        ]

        yc_train = [
            partite[j]["gol_casa"]
            - partite[j]["baseline_casa"]
            for j in range(i)
            if math.isfinite(valori[j])
        ]

        yo_train = [
            partite[j]["gol_ospite"]
            - partite[j]["baseline_ospite"]
            for j in range(i)
            if math.isfinite(valori[j])
        ]


        if len(X_train) < 3:

            correzione_casa = 0.0
            correzione_ospite = 0.0

        else:

            modello_casa = LinearRegression()
            modello_ospite = LinearRegression()

            modello_casa.fit(X_train, yc_train)
            modello_ospite.fit(X_train, yo_train)

            x_test = [[valori[i]]]

            correzione_casa = float(
                modello_casa.predict(x_test)[0]
            )

            correzione_ospite = float(
                modello_ospite.predict(x_test)[0]
            )


        pred_casa = max(
            0.0,
            attuale["baseline_casa"]
            + correzione_casa
        )

        pred_ospite = max(
            0.0,
            attuale["baseline_ospite"]
            + correzione_ospite
        )


        predizioni.append({
            **attuale,
            "pred_casa": pred_casa,
            "pred_ospite": pred_ospite,
        })


    mae, rmse = valuta(predizioni)

    print(
        f"{nome:25s} "
        f"MAE={mae:.4f} "
        f"RMSE={rmse:.4f} "
        f"dMAE={mae - mae_base:+.4f} "
        f"dRMSE={rmse - rmse_base:+.4f}"
    )


print()
print("==============================================")
print(" BASELINE DI RIFERIMENTO")
print("==============================================")
print(f"MAE  = {mae_base:.4f}")
print(f"RMSE = {rmse_base:.4f}")
print()
print("Benchmark ufficiale atteso:")
print("MAE  = 0.7683")
print("RMSE = 0.9473")
