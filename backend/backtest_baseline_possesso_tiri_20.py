import csv
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error

FEATURES = "../data/serie_a_features.csv"
BASELINE = "../data/serie_a_backtest_baseline.csv"
OUTPUT = "../data/serie_a_backtest_baseline_possesso_tiri_20.csv"


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

    possesso_casa = numero(f["casa_possesso_totale_pre"])
    possesso_ospite = numero(f["ospite_possesso_totale_pre"])

    tiri_casa = numero(f["casa_tiri_in_porta_totale_pre"])
    tiri_ospite = numero(f["ospite_tiri_in_porta_totale_pre"])

    if None in (
        possesso_casa,
        possesso_ospite,
        tiri_casa,
        tiri_ospite
    ):
        raise RuntimeError(
            f"Dati mancanti per: {chiave}"
        )

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
        "tiri_casa": tiri_casa,
        "tiri_ospite": tiri_ospite,
    })


# --------------------------------------------------
# VARIABILI
#
# 1. differenziale possesso
# 2. differenziale tiri in porta
#
# Il modello impara automaticamente la relazione
# tra queste variabili e l'errore del baseline.
# Nessun peso viene deciso manualmente.
# --------------------------------------------------

X = [
    [
        p["possesso_casa"] - p["possesso_ospite"],
        p["tiri_casa"] - p["tiri_ospite"]
    ]
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


# --------------------------------------------------
# LEAVE-ONE-OUT
#
# Ogni partita viene prevista utilizzando un modello
# addestrato sulle altre 19.
# --------------------------------------------------

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
        "possesso_casa": attuale["possesso_casa"],
        "possesso_ospite": attuale["possesso_ospite"],
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


print("\n===== BASELINE + POSSESSO + TIRI IN PORTA =====")
print(f"Partite utilizzate: {len(predizioni)}")

print(f"MAE gol casa: {mae_casa:.4f}")
print(f"MAE gol ospite: {mae_ospite:.4f}")
print(f"MAE medio: {mae_medio:.4f}")

print(f"RMSE gol casa: {rmse_casa:.4f}")
print(f"RMSE gol ospite: {rmse_ospite:.4f}")
print(f"RMSE medio: {rmse_medio:.4f}")

print("\n===== CONFRONTO =====")

print("Baseline:")
print("MAE medio:  0.7683")
print("RMSE medio: 0.9473")

print("\nBaseline + Possesso:")
print("MAE medio:  0.7770")
print("RMSE medio: 0.9027")

print("\nBaseline + Tiri in porta:")
print("MAE medio:  0.7685")
print("RMSE medio: 0.9251")

print("\nBaseline + Possesso + Tiri in porta:")
print(f"MAE medio:  {mae_medio:.4f}")
print(f"RMSE medio: {rmse_medio:.4f}")

print("\n===== DIFFERENZA DAL BASELINE =====")
print(f"MAE:  {mae_medio - 0.7683:+.4f}")
print(f"RMSE: {rmse_medio - 0.9473:+.4f}")

print(f"\nFile salvato: {OUTPUT}")
