import csv
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error

FEATURES = "../data/serie_a_features.csv"
BASELINE = "../data/serie_a_backtest_baseline.csv"
OUTPUT = "../data/serie_a_backtest_baseline_tiri_in_porta_20.csv"


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

    tiri_casa = numero(f["casa_tiri_in_porta_totale_pre"])
    tiri_ospite = numero(f["ospite_tiri_in_porta_totale_pre"])

    if tiri_casa is None or tiri_ospite is None:
        raise RuntimeError(
            f"Tiri in porta mancanti per: {chiave}"
        )

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


# Differenziale dei tiri in porta.
X = [
    [p["tiri_casa"] - p["tiri_ospite"]]
    for p in partite
]

# Errore del baseline che vogliamo correggere.
y_casa = [
    p["gol_casa"] - p["baseline_casa"]
    for p in partite
]

y_ospite = [
    p["gol_ospite"] - p["baseline_ospite"]
    for p in partite
]


# Leave-One-Out:
# ogni partita viene prevista senza utilizzare
# il proprio risultato nell'addestramento.
predizioni = []

for i, attuale in enumerate(partite):

    X_train = X[:i] + X[i + 1:]
    yc_train = y_casa[:i] + y_casa[i + 1:]
    yo_train = y_ospite[:i] + y_ospite[i + 1:]

    modello_casa = LinearRegression()
    modello_ospite = LinearRegression()

    modello_casa.fit(X_train, yc_train)
    modello_ospite.fit(X_train, yo_train)

    X_test = [X[i]]

    correzione_casa = float(
        modello_casa.predict(X_test)[0]
    )

    correzione_ospite = float(
        modello_ospite.predict(X_test)[0]
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
        "data": attuale["data"],
        "casa": attuale["casa"],
        "ospite": attuale["ospite"],
        "gol_casa_reali": attuale["gol_casa"],
        "gol_ospite_reali": attuale["gol_ospite"],
        "baseline_casa": attuale["baseline_casa"],
        "baseline_ospite": attuale["baseline_ospite"],
        "tiri_in_porta_casa": attuale["tiri_casa"],
        "tiri_in_porta_ospite": attuale["tiri_ospite"],
        "gol_casa_attesi": round(pred_casa, 4),
        "gol_ospite_attesi": round(pred_ospite, 4),
    })


with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=predizioni[0].keys()
    )
    writer.writeheader()
    writer.writerows(predizioni)


yc = [p["gol_casa_reali"] for p in predizioni]
yo = [p["gol_ospite_reali"] for p in predizioni]

pc = [p["gol_casa_attesi"] for p in predizioni]
po = [p["gol_ospite_attesi"] for p in predizioni]

mae_casa = mean_absolute_error(yc, pc)
mae_ospite = mean_absolute_error(yo, po)

rmse_casa = mean_squared_error(yc, pc) ** 0.5
rmse_ospite = mean_squared_error(yo, po) ** 0.5

mae_medio = (mae_casa + mae_ospite) / 2
rmse_medio = (rmse_casa + rmse_ospite) / 2


print("\n===== BASELINE + TIRI IN PORTA - 20 PARTITE =====")
print(f"Partite utilizzate: {len(predizioni)}")

print(f"MAE gol casa: {mae_casa:.4f}")
print(f"MAE gol ospite: {mae_ospite:.4f}")
print(f"MAE medio: {mae_medio:.4f}")

print(f"RMSE gol casa: {rmse_casa:.4f}")
print(f"RMSE gol ospite: {rmse_ospite:.4f}")
print(f"RMSE medio: {rmse_medio:.4f}")

print("\n===== CONFRONTO =====")
print("Baseline MAE medio:  0.7683")
print(f"Nuovo MAE medio:      {mae_medio:.4f}")
print(f"Differenza MAE:       {mae_medio - 0.7683:+.4f}")

print("Baseline RMSE medio: 0.9473")
print(f"Nuovo RMSE medio:     {rmse_medio:.4f}")
print(f"Differenza RMSE:      {rmse_medio - 0.9473:+.4f}")

print(f"\nFile salvato: {OUTPUT}")
