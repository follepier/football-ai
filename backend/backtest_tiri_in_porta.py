import csv
import sys
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error

sys.path.insert(0, ".")

from app.services.baseline import stima_gol_attesi

FEATURES = "../data/serie_a_features.csv"
BASELINE = "../data/serie_a_backtest_baseline.csv"
OUTPUT = "../data/serie_a_backtest_tiri_in_porta.csv"


def numero(valore):
    if valore in ("", None):
        return None
    return float(valore)


# Carichiamo le feature pre-partita
with open(FEATURES, encoding="utf-8") as f:
    features = list(csv.DictReader(f))

# Usiamo ESATTAMENTE le 20 partite del baseline
with open(BASELINE, encoding="utf-8") as f:
    baseline = list(csv.DictReader(f))


# Indicizziamo le feature per data + squadre
indice = {}

for r in features:
    chiave = (r["data"], r["casa"], r["ospite"])
    indice[chiave] = r


risultati = []

for r in baseline:
    chiave = (r["data"], r["casa"], r["ospite"])
    partita = indice.get(chiave)

    if partita is None:
        continue

    tiri_casa = numero(partita["casa_tiri_in_porta_totale_pre"])
    tiri_ospite = numero(partita["ospite_tiri_in_porta_totale_pre"])

    if tiri_casa is None or tiri_ospite is None:
        continue

    risultati.append({
        "data": r["data"],
        "casa": r["casa"],
        "ospite": r["ospite"],
        "gol_casa_reali": int(r["gol_casa_reali"]),
        "gol_ospite_reali": int(r["gol_ospite_reali"]),
        "tiri_casa": tiri_casa,
        "tiri_ospite": tiri_ospite,
    })


if len(risultati) != len(baseline):
    print(
        f"ATTENZIONE: baseline={len(baseline)} "
        f"partite, tiri in porta={len(risultati)}"
    )


# Modello statistico:
# stimiamo dai dati precedenti quanto i tiri in porta
# siano associati ai gol.
predizioni = []

for i, attuale in enumerate(risultati):

    precedenti = risultati[:i]

    if len(precedenti) < 5:
        continue

    X = [
        [r["tiri_casa"], r["tiri_ospite"]]
        for r in precedenti
    ]

    y_casa = [r["gol_casa_reali"] for r in precedenti]
    y_ospite = [r["gol_ospite_reali"] for r in precedenti]

    modello_casa = LinearRegression()
    modello_ospite = LinearRegression()

    modello_casa.fit(X, y_casa)
    modello_ospite.fit(X, y_ospite)

    X_test = [[
        attuale["tiri_casa"],
        attuale["tiri_ospite"]
    ]]

    pred_casa = max(
        0.0,
        float(modello_casa.predict(X_test)[0])
    )

    pred_ospite = max(
        0.0,
        float(modello_ospite.predict(X_test)[0])
    )

    predizioni.append({
        "data": attuale["data"],
        "casa": attuale["casa"],
        "ospite": attuale["ospite"],
        "gol_casa_reali": attuale["gol_casa_reali"],
        "gol_ospite_reali": attuale["gol_ospite_reali"],
        "tiri_casa": attuale["tiri_casa"],
        "tiri_ospite": attuale["tiri_ospite"],
        "gol_casa_attesi": round(pred_casa, 4),
        "gol_ospite_attesi": round(pred_ospite, 4),
    })


if not predizioni:
    raise RuntimeError(
        "Nessuna predizione disponibile per il backtest."
    )


with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    campi = predizioni[0].keys()
    writer = csv.DictWriter(f, fieldnames=campi)
    writer.writeheader()
    writer.writerows(predizioni)


y_casa = [r["gol_casa_reali"] for r in predizioni]
y_ospite = [r["gol_ospite_reali"] for r in predizioni]

p_casa = [r["gol_casa_attesi"] for r in predizioni]
p_ospite = [r["gol_ospite_attesi"] for r in predizioni]

mae_casa = mean_absolute_error(y_casa, p_casa)
mae_ospite = mean_absolute_error(y_ospite, p_ospite)

rmse_casa = mean_squared_error(y_casa, p_casa) ** 0.5
rmse_ospite = mean_squared_error(y_ospite, p_ospite) ** 0.5

print("\n===== BACKTEST TIRI IN PORTA =====")
print(f"Partite utilizzate: {len(predizioni)}")
print(f"MAE gol casa: {mae_casa:.4f}")
print(f"MAE gol ospite: {mae_ospite:.4f}")
print(f"MAE medio: {(mae_casa + mae_ospite) / 2:.4f}")
print(f"RMSE gol casa: {rmse_casa:.4f}")
print(f"RMSE gol ospite: {rmse_ospite:.4f}")
print(f"RMSE medio: {(rmse_casa + rmse_ospite) / 2:.4f}")

print(f"\nFile salvato: {OUTPUT}")
