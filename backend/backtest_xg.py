import csv
import sys
from sklearn.metrics import mean_absolute_error, mean_squared_error

sys.path.insert(0, ".")

from app.services.baseline import stima_gol_attesi

FILE = "../data/serie_a_features.csv"
OUTPUT = "../data/serie_a_backtest_xg.csv"


def numero(valore):
    if valore in ("", None):
        return None
    return float(valore)


with open(FILE, encoding="utf-8") as f:
    partite = list(csv.DictReader(f))


risultati = []

for partita in partite:

    casa_xgf = numero(partita["casa_xg_fatti_totale_pre"])
    casa_xgs = numero(partita["casa_xg_subiti_totale_pre"])

    ospite_xgf = numero(partita["ospite_xg_fatti_totale_pre"])
    ospite_xgs = numero(partita["ospite_xg_subiti_totale_pre"])

    storico_casa = int(partita["casa_partite_totale_pre"])
    storico_ospite = int(partita["ospite_partite_totale_pre"])

    if (
        casa_xgf is None
        or casa_xgs is None
        or ospite_xgf is None
        or ospite_xgs is None
    ):
        continue

    media_campionato = 1.5

    xg_casa_attesi, xg_ospite_attesi = stima_gol_attesi(
        casa_xgf,
        casa_xgs,
        ospite_xgf,
        ospite_xgs,
        media_campionato,
        storico_casa,
        storico_ospite
    )

    risultati.append({
        "data": partita["data"],
        "casa": partita["casa"],
        "ospite": partita["ospite"],
        "gol_casa_reali": int(partita["gol_casa"]),
        "gol_ospite_reali": int(partita["gol_ospite"]),
        "xg_casa_attesi": xg_casa_attesi,
        "xg_ospite_attesi": xg_ospite_attesi,
        "storico_casa": storico_casa,
        "storico_ospite": storico_ospite
    })


if not risultati:
    raise RuntimeError("Nessuna partita disponibile per il backtest xG.")


with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    campi = risultati[0].keys()
    writer = csv.DictWriter(f, fieldnames=campi)
    writer.writeheader()
    writer.writerows(risultati)


y_casa = [r["gol_casa_reali"] for r in risultati]
y_ospite = [r["gol_ospite_reali"] for r in risultati]

pred_casa = [r["xg_casa_attesi"] for r in risultati]
pred_ospite = [r["xg_ospite_attesi"] for r in risultati]

mae_casa = mean_absolute_error(y_casa, pred_casa)
mae_ospite = mean_absolute_error(y_ospite, pred_ospite)

rmse_casa = mean_squared_error(y_casa, pred_casa) ** 0.5
rmse_ospite = mean_squared_error(y_ospite, pred_ospite) ** 0.5


print("\n===== BACKTEST MODELLO xG =====")
print(f"Partite utilizzate: {len(risultati)}")
print(f"MAE gol casa: {mae_casa:.4f}")
print(f"MAE gol ospite: {mae_ospite:.4f}")
print(f"MAE medio: {(mae_casa + mae_ospite) / 2:.4f}")
print(f"RMSE gol casa: {rmse_casa:.4f}")
print(f"RMSE gol ospite: {rmse_ospite:.4f}")
print(f"RMSE medio: {(rmse_casa + rmse_ospite) / 2:.4f}")
print(f"\nFile salvato: {OUTPUT}")
