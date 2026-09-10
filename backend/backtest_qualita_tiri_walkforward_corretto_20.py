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

    tiri_porta_casa = numero(f["casa_tiri_in_porta_totale_pre"])
    tiri_porta_ospite = numero(f["ospite_tiri_in_porta_totale_pre"])

    tiri_fuori_casa = numero(f["casa_tiri_fuori_totale_pre"])
    tiri_fuori_ospite = numero(f["ospite_tiri_fuori_totale_pre"])

    xgf_casa = numero(f["casa_xg_fatti_totale_pre"])
    xgf_ospite = numero(f["ospite_xg_fatti_totale_pre"])

    if None in (
        tiri_porta_casa,
        tiri_porta_ospite,
        tiri_fuori_casa,
        tiri_fuori_ospite,
        xgf_casa,
        xgf_ospite,
    ):
        continue

    totale_casa = tiri_porta_casa + tiri_fuori_casa
    totale_ospite = tiri_porta_ospite + tiri_fuori_ospite

    precisione_casa = (
        tiri_porta_casa / totale_casa
        if totale_casa > 0 else 0.0
    )

    precisione_ospite = (
        tiri_porta_ospite / totale_ospite
        if totale_ospite > 0 else 0.0
    )

    xg_per_tiro_casa = (
        xgf_casa / totale_casa
        if totale_casa > 0 else 0.0
    )

    xg_per_tiro_ospite = (
        xgf_ospite / totale_ospite
        if totale_ospite > 0 else 0.0
    )

    partite.append({
        "data": b["data"],
        "casa": b["casa"],
        "ospite": b["ospite"],
        "gol_casa": float(b["gol_casa_reali"]),
        "gol_ospite": float(b["gol_ospite_reali"]),
        "baseline_casa": float(b["gol_casa_attesi"]),
        "baseline_ospite": float(b["gol_ospite_attesi"]),

        "precisione_diff":
            precisione_casa - precisione_ospite,

        "xg_per_tiro_diff":
            xg_per_tiro_casa - xg_per_tiro_ospite,

        "volume_diff":
            totale_casa - totale_ospite,

        "tiri_porta_diff":
            tiri_porta_casa - tiri_porta_ospite,
    })


# ============================================================
# TEST WALK-FORWARD
# ============================================================

variabili = {
    "precisione": "precisione_diff",
    "xg_per_tiro": "xg_per_tiro_diff",
    "volume_tiri": "volume_diff",
    "tiri_in_porta": "tiri_porta_diff",
}

risultati = {}


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


# Baseline pura
baseline_pred = []

for p in partite:
    baseline_pred.append({
        **p,
        "pred_casa": max(0.0, p["baseline_casa"]),
        "pred_ospite": max(0.0, p["baseline_ospite"]),
    })

risultati["baseline"] = valuta(baseline_pred)


# Walk-forward:
# la partita i viene prevista usando SOLO le partite precedenti.
for nome, campo in variabili.items():

    predizioni = []

    for i, attuale in enumerate(partite):

        # Servono almeno 3 osservazioni storiche
        # per evitare regressioni troppo instabili.
        if i < 3:
            predizioni.append({
                **attuale,
                "pred_casa":
                    max(0.0, attuale["baseline_casa"]),
                "pred_ospite":
                    max(0.0, attuale["baseline_ospite"]),
            })
            continue

        storiche = partite[:i]

        X_train = [
            [s[campo]]
            for s in storiche
            if math.isfinite(s[campo])
        ]

        yc_train = [
            s["gol_casa"] - s["baseline_casa"]
            for s in storiche
            if math.isfinite(s[campo])
        ]

        yo_train = [
            s["gol_ospite"] - s["baseline_ospite"]
            for s in storiche
            if math.isfinite(s[campo])
        ]

        if len(X_train) < 3:
            correzione_casa = 0.0
            correzione_ospite = 0.0
        else:
            modello_casa = LinearRegression()
            modello_ospite = LinearRegression()

            modello_casa.fit(X_train, yc_train)
            modello_ospite.fit(X_train, yo_train)

            x_test = [[attuale[campo]]]

            correzione_casa = float(
                modello_casa.predict(x_test)[0]
            )

            correzione_ospite = float(
                modello_ospite.predict(x_test)[0]
            )

        pred_casa = max(
            0.0,
            attuale["baseline_casa"] + correzione_casa
        )

        pred_ospite = max(
            0.0,
            attuale["baseline_ospite"] + correzione_ospite
        )

        predizioni.append({
            **attuale,
            "pred_casa": pred_casa,
            "pred_ospite": pred_ospite,
        })

    risultati[nome] = valuta(predizioni)


# ============================================================
# OUTPUT
# ============================================================

mae_base, rmse_base = risultati["baseline"]

print()
print("==========================================")
print(" QUALITA' TIRI - WALK-FORWARD CORRETTO")
print("==========================================")
print(f"Partite utilizzate: {len(partite)}")
print()

for nome, (mae, rmse) in risultati.items():

    print(
        f"{nome:25s} "
        f"MAE={mae:.4f} "
        f"RMSE={rmse:.4f} "
        f"dMAE={mae - mae_base:+.4f} "
        f"dRMSE={rmse - rmse_base:+.4f}"
    )

print()
print("==========================================")
print(" RIFERIMENTO BENCHMARK UFFICIALE")
print("==========================================")
print("MAE ufficiale:  0.7683")
print("RMSE ufficiale: 0.9473")
print()

print("NOTA:")
print("- Walk-forward: nessun risultato futuro utilizzato.")
print("- Baseline ufficiale invariata.")
print("- Nessuna variabile viene inserita nel modello principale.")
