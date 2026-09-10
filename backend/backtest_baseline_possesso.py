import csv
import math
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error

FEATURES = "../data/serie_a_features.csv"
BASELINE = "../data/serie_a_backtest_baseline.csv"
OUTPUT = "../data/serie_a_backtest_baseline_possesso.csv"


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
        continue

    possesso_casa = numero(f["casa_possesso_totale_pre"])
    possesso_ospite = numero(f["ospite_possesso_totale_pre"])

    if possesso_casa is None or possesso_ospite is None:
        continue

    partite.append({
        "data": b["data"],
        "casa": b["casa"],
        "ospite": b["ospite"],
        "gol_casa": float(b["gol_casa_reali"]),
        "gol_ospite": float(b["gol_ospite_reali"]),
        "baseline_casa": float(b["gol_casa_attesi"]),
        "baseline_ospite": float(b["gol_ospite_attesi"]),
        "possesso_casa": possesso_casa,
        "possesso_ospite": possesso_ospite,
    })


predizioni = []

# Walk-forward:
# per ogni partita usiamo soltanto le partite precedenti
# per stimare quanto il possesso corregge il baseline.
for i, attuale in enumerate(partite):

    precedenti = partite[:i]

    if len(precedenti) < 5:
        continue

    # Variabile esplicativa:
    # differenza di possesso tra casa e ospite.
    X = [
        [p["possesso_casa"] - p["possesso_ospite"]]
        for p in precedenti
    ]

    # Correzione reale rispetto al baseline.
    y_casa = [
        p["gol_casa"] - p["baseline_casa"]
        for p in precedenti
    ]

    y_ospite = [
        p["gol_ospite"] - p["baseline_ospite"]
        for p in precedenti
    ]

    modello_casa = LinearRegression()
    modello_ospite = LinearRegression()

    modello_casa.fit(X, y_casa)
    modello_ospite.fit(X, y_ospite)

    differenza_possesso = (
        attuale["possesso_casa"]
        - attuale["possesso_ospite"]
    )

    X_test = [[differenza_possesso]]

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
        "possesso_casa": attuale["possesso_casa"],
        "possesso_ospite": attuale["possesso_ospite"],
        "gol_casa_attesi": round(pred_casa, 4),
        "gol_ospite_attesi": round(pred_ospite, 4),
    })


if not predizioni:
    raise RuntimeError("Nessuna predizione disponibile.")


with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=predizioni[0].keys()
    )
    writer.writeheader()
    writer.writerows(predizioni)


# Valutazione
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


print("\n===== BACKTEST BASELINE + POSSESSO =====")
print(f"Partite utilizzate: {len(predizioni)}")

print(f"MAE gol casa: {mae_casa:.4f}")
print(f"MAE gol ospite: {mae_ospite:.4f}")
print(f"MAE medio: {mae_medio:.4f}")

print(f"RMSE gol casa: {rmse_casa:.4f}")
print(f"RMSE gol ospite: {rmse_ospite:.4f}")
print(f"RMSE medio: {rmse_medio:.4f}")

print("\n===== CONFRONTO CON BASELINE =====")
print("Baseline MAE medio:  0.7683")
print(f"Possesso MAE medio:   {mae_medio:.4f}")
print(f"Differenza MAE:       {mae_medio - 0.7683:+.4f}")

print("Baseline RMSE medio: 0.9473")
print(f"Possesso RMSE medio:  {rmse_medio:.4f}")
print(f"Differenza RMSE:      {rmse_medio - 0.9473:+.4f}")

if mae_medio < 0.7683:
    print("\nRISULTATO MAE: IL POSSESSO MIGLIORA IL BASELINE")
elif mae_medio > 0.7683:
    print("\nRISULTATO MAE: IL POSSESSO PEGGIORA IL BASELINE")
else:
    print("\nRISULTATO MAE: PARITA'")

if rmse_medio < 0.9473:
    print("RISULTATO RMSE: IL POSSESSO MIGLIORA IL BASELINE")
elif rmse_medio > 0.9473:
    print("RISULTATO RMSE: IL POSSESSO PEGGIORA IL BASELINE")
else:
    print("RISULTATO RMSE: PARITA'")

print(f"\nFile salvato: {OUTPUT}")
