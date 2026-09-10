import csv
import sys
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error

sys.path.insert(0, ".")

from app.services.baseline import stima_gol_attesi

FILE = "../data/serie_a_features.csv"
OUTPUT = "../data/serie_a_backtest_possesso.csv"


def numero(valore):
    if valore in ("", None):
        return None
    return float(valore)


with open(FILE, encoding="utf-8") as f:
    partite = list(csv.DictReader(f))


# Usiamo solo partite con tutte le informazioni necessarie.
dati = []

for partita in partite:
    valori = [
        partita["casa_possesso_totale_pre"],
        partita["ospite_possesso_totale_pre"],
        partita["gol_casa"],
        partita["gol_ospite"],
    ]

    if any(v in ("", None) for v in valori):
        continue

    dati.append({
        "data": partita["data"],
        "casa": partita["casa"],
        "ospite": partita["ospite"],
        "possesso_casa": numero(partita["casa_possesso_totale_pre"]),
        "possesso_ospite": numero(partita["ospite_possesso_totale_pre"]),
        "gol_casa": int(partita["gol_casa"]),
        "gol_ospite": int(partita["gol_ospite"]),
    })


risultati = []

# Walk-forward:
# per ogni partita stimiamo il rapporto tra possesso e gol
# usando SOLO le partite precedenti.
for i in range(1, len(dati)):

    precedente = dati[:i]
    attuale = dati[i]

    X = []
    y_casa = []
    y_ospite = []

    for r in precedente:
        X.append([
            r["possesso_casa"],
            r["possesso_ospite"],
        ])
        y_casa.append(r["gol_casa"])
        y_ospite.append(r["gol_ospite"])

    # Servono almeno alcune osservazioni per stimare il modello.
    if len(precedente) < 5:
        continue

    modello_casa = LinearRegression()
    modello_ospite = LinearRegression()

    modello_casa.fit(X, y_casa)
    modello_ospite.fit(X, y_ospite)

    X_test = [[
        attuale["possesso_casa"],
        attuale["possesso_ospite"],
    ]]

    pred_casa = max(0.0, float(modello_casa.predict(X_test)[0]))
    pred_ospite = max(0.0, float(modello_ospite.predict(X_test)[0]))

    risultati.append({
        "data": attuale["data"],
        "casa": attuale["casa"],
        "ospite": attuale["ospite"],
        "gol_casa_reali": attuale["gol_casa"],
        "gol_ospite_reali": attuale["gol_ospite"],
        "possesso_casa": attuale["possesso_casa"],
        "possesso_ospite": attuale["possesso_ospite"],
        "gol_casa_attesi": round(pred_casa, 4),
        "gol_ospite_attesi": round(pred_ospite, 4),
    })


if not risultati:
    raise RuntimeError("Nessuna partita disponibile per il backtest possesso.")


with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    campi = risultati[0].keys()
    writer = csv.DictWriter(f, fieldnames=campi)
    writer.writeheader()
    writer.writerows(risultati)


y_casa = [r["gol_casa_reali"] for r in risultati]
y_ospite = [r["gol_ospite_reali"] for r in risultati]

pred_casa = [r["gol_casa_attesi"] for r in risultati]
pred_ospite = [r["gol_ospite_attesi"] for r in risultati]

mae_casa = mean_absolute_error(y_casa, pred_casa)
mae_ospite = mean_absolute_error(y_ospite, pred_ospite)

rmse_casa = mean_squared_error(y_casa, pred_casa) ** 0.5
rmse_ospite = mean_squared_error(y_ospite, pred_ospite) ** 0.5

print("\n===== BACKTEST POSSESSO =====")
print(f"Partite utilizzate: {len(risultati)}")
print(f"MAE gol casa: {mae_casa:.4f}")
print(f"MAE gol ospite: {mae_ospite:.4f}")
print(f"MAE medio: {(mae_casa + mae_ospite) / 2:.4f}")
print(f"RMSE gol casa: {rmse_casa:.4f}")
print(f"RMSE gol ospite: {rmse_ospite:.4f}")
print(f"RMSE medio: {(rmse_casa + rmse_ospite) / 2:.4f}")

print(f"\nFile salvato: {OUTPUT}")
