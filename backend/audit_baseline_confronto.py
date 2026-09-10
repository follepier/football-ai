import pandas as pd
import numpy as np

FEATURES = "data/serie_a_features.csv"
DATASET = "data/serie_a_dataset.csv"

features = pd.read_csv(FEATURES)
dataset = pd.read_csv(DATASET)

features["data"] = pd.to_datetime(features["data"])
dataset["data"] = pd.to_datetime(dataset["data"])

features = features.sort_values("data").reset_index(drop=True)
dataset = dataset.sort_values("data").reset_index(drop=True)

if len(features) != len(dataset):
    raise ValueError(
        f"Righe diverse: features={len(features)}, dataset={len(dataset)}"
    )

df = features.copy()
df["gol_casa"] = dataset["gol_casa"]
df["gol_ospite"] = dataset["gol_ospite"]

df = df.sort_values("data").reset_index(drop=True)

test = df.tail(20).copy()


def stabilizza(media_squadra, numero_partite, media_campionato):
    numero_partite = max(numero_partite, 0)

    if media_campionato <= 0:
        media_campionato = 1.0

    return (
        numero_partite * media_squadra
        + media_campionato
    ) / (numero_partite + 1)


def baseline(
    casa_gf,
    casa_gs,
    ospite_gf,
    ospite_gs,
    media,
    n_casa=1,
    n_ospite=1
):
    ca = stabilizza(casa_gf, n_casa, media)
    cd = stabilizza(casa_gs, n_casa, media)
    oa = stabilizza(ospite_gf, n_ospite, media)
    od = stabilizza(ospite_gs, n_ospite, media)

    gh = ca * od / media
    ga = oa * cd / media

    return gh, ga


print("\n======================================")
print(" AUDIT BASELINE - 20 PARTITE")
print("======================================\n")

pred_home = []
pred_away = []

for i in range(20):

    row = test.iloc[i]

    # Tutto ciò che è disponibile prima della partita
    storico = df.iloc[:len(df) - 20 + i]

    media = (
        storico["gol_casa"].sum()
        + storico["gol_ospite"].sum()
    ) / (2 * len(storico))

    gh, ga = baseline(
        row["casa_gol_fatti_totale_pre"],
        row["casa_gol_subiti_totale_pre"],
        row["ospite_gol_fatti_totale_pre"],
        row["ospite_gol_subiti_totale_pre"],
        media
    )

    pred_home.append(gh)
    pred_away.append(ga)

    print(
        f"{row['data'].date()} "
        f"{i+1:02d} | "
        f"Reale {row['gol_casa']:.0f}-{row['gol_ospite']:.0f} | "
        f"Atteso {gh:.4f}-{ga:.4f} | "
        f"Media={media:.4f}"
    )


pred_home = np.array(pred_home)
pred_away = np.array(pred_away)

real_home = test["gol_casa"].to_numpy()
real_away = test["gol_ospite"].to_numpy()

mae_home = np.mean(np.abs(pred_home - real_home))
mae_away = np.mean(np.abs(pred_away - real_away))

rmse_home = np.sqrt(np.mean((pred_home - real_home) ** 2))
rmse_away = np.sqrt(np.mean((pred_away - real_away) ** 2))

print("\n--------------------------------------")
print(f"MAE CASA  = {mae_home:.4f}")
print(f"MAE OSPITE = {mae_away:.4f}")
print(f"MAE MEDIO  = {(mae_home + mae_away)/2:.4f}")
print()
print(f"RMSE CASA  = {rmse_home:.4f}")
print(f"RMSE OSPITE = {rmse_away:.4f}")
print(f"RMSE MEDIO  = {(rmse_home + rmse_away)/2:.4f}")
print("--------------------------------------")
