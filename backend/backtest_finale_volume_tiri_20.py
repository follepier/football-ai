import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.linear_model import LinearRegression

BASELINE_FILE = Path("data/serie_a_backtest_baseline.csv")
FEATURES_FILE = Path("data/serie_a_features.csv")
OUTPUT_FILE = Path("data/serie_a_backtest_finale_volume_tiri_20.csv")


def metriche(yh, ya, ph, pa):
    err_h = np.array(ph) - np.array(yh)
    err_a = np.array(pa) - np.array(ya)

    mae_h = np.mean(np.abs(err_h))
    mae_a = np.mean(np.abs(err_a))
    rmse_h = np.sqrt(np.mean(err_h ** 2))
    rmse_a = np.sqrt(np.mean(err_a ** 2))

    return {
        "mae_home": mae_h,
        "mae_away": mae_a,
        "mae_mean": (mae_h + mae_a) / 2,
        "rmse_home": rmse_h,
        "rmse_away": rmse_a,
        "rmse_mean": (rmse_h + rmse_a) / 2,
    }


def baseline(gf_h, ga_h, gf_a, ga_a, media):
    if media <= 0:
        media = 1.0

    def stabilizza(x):
        return (x + media) / 2

    att_h = stabilizza(gf_h)
    dif_h = stabilizza(ga_h)
    att_a = stabilizza(gf_a)
    dif_a = stabilizza(ga_a)

    return (
        att_h * dif_a / media,
        att_a * dif_h / media,
    )


print("=" * 70)
print("BACKTEST FINALE - BASELINE + VOLUME TIRI")
print("=" * 70)

base = pd.read_csv(BASELINE_FILE)
features = pd.read_csv(FEATURES_FILE)

base["data"] = pd.to_datetime(base["data"])
features["data"] = pd.to_datetime(features["data"])

# Normalizzazione nomi squadre
for df in (base, features):
    df["casa"] = df["casa"].astype(str).str.strip()
    df["ospite"] = df["ospite"].astype(str).str.strip()

# Individua automaticamente le colonne del volume tiri
required = [
    "casa_tiri_in_porta_totale_pre",
    "ospite_tiri_in_porta_totale_pre",
    "casa_tiri_fuori_totale_pre",
    "ospite_tiri_fuori_totale_pre",
]

for col in required:
    if col not in features.columns:
        raise SystemExit(f"Colonna mancante: {col}")

# Volume totale tiri = tiri in porta + tiri fuori
features["volume_tiri_casa"] = (
    features["casa_tiri_in_porta_totale_pre"].fillna(0)
    + features["casa_tiri_fuori_totale_pre"].fillna(0)
)

features["volume_tiri_ospite"] = (
    features["ospite_tiri_in_porta_totale_pre"].fillna(0)
    + features["ospite_tiri_fuori_totale_pre"].fillna(0)
)

# Unione esclusivamente sulle partite del benchmark
df = base.merge(
    features[
        [
            "data",
            "casa",
            "ospite",
            "volume_tiri_casa",
            "volume_tiri_ospite",
        ]
    ],
    on=["data", "casa", "ospite"],
    how="left",
)

if len(df) != len(base):
    raise SystemExit("ERRORE: numero partite cambiato durante il merge.")

if df["volume_tiri_casa"].isna().any() or df["volume_tiri_ospite"].isna().any():
    missing = df[
        df["volume_tiri_casa"].isna()
        | df["volume_tiri_ospite"].isna()
    ][["data", "casa", "ospite"]]

    print("Partite senza volume tiri:")
    print(missing.to_string(index=False))
    raise SystemExit("ERRORE: dati volume tiri mancanti.")

print(f"Partite benchmark: {len(df)}")

# ------------------------------------------------------------
# 1. BASELINE
# ------------------------------------------------------------

yh = df["gol_casa_reali"].tolist()
ya = df["gol_ospite_reali"].tolist()

ph_base = df["gol_casa_attesi"].tolist()
pa_base = df["gol_ospite_attesi"].tolist()

m_base = metriche(yh, ya, ph_base, pa_base)

# ------------------------------------------------------------
# 2. BASELINE + VOLUME TIRI
# ------------------------------------------------------------
#
# Usiamo esclusivamente la relazione tra:
#   volume tiri pre-match
# e
#   errore residuo della baseline.
#
# Per ogni partita il correttore viene addestrato soltanto
# sulle partite precedenti (walk-forward).
# ------------------------------------------------------------

res_h = []
res_a = []

ph_vol = []
pa_vol = []

for i in range(len(df)):
    # Non possiamo addestrare un correttore senza storico.
    if i < 3:
        ph_vol.append(ph_base[i])
        pa_vol.append(pa_base[i])

        res_h.append(yh[i] - ph_base[i])
        res_a.append(ya[i] - pa_base[i])
        continue

    train = df.iloc[:i]

    X_train = train[
        ["volume_tiri_casa", "volume_tiri_ospite"]
    ].values

    y_train_h = np.array(yh[:i]) - np.array(ph_base[:i])
    y_train_a = np.array(ya[:i]) - np.array(pa_base[:i])

    model_h = LinearRegression()
    model_a = LinearRegression()

    model_h.fit(X_train, y_train_h)
    model_a.fit(X_train, y_train_a)

    X_test = df.iloc[[i]][
        ["volume_tiri_casa", "volume_tiri_ospite"]
    ].values

    correction_h = model_h.predict(X_test)[0]
    correction_a = model_a.predict(X_test)[0]

    ph_vol.append(ph_base[i] + correction_h)
    pa_vol.append(pa_base[i] + correction_a)

    res_h.append(yh[i] - ph_vol[-1])
    res_a.append(ya[i] - pa_vol[-1])

m_vol = metriche(yh, ya, ph_vol, pa_vol)

# ------------------------------------------------------------
# RISULTATI
# ------------------------------------------------------------

print()
print("=" * 70)
print("BASELINE")
print("=" * 70)

for k, v in m_base.items():
    print(f"{k:12s}: {v:.4f}")

print()
print("=" * 70)
print("BASELINE + VOLUME TIRI")
print("=" * 70)

for k, v in m_vol.items():
    print(f"{k:12s}: {v:.4f}")

print()
print("=" * 70)
print("CONFRONTO")
print("=" * 70)

delta_mae = m_vol["mae_mean"] - m_base["mae_mean"]
delta_rmse = m_vol["rmse_mean"] - m_base["rmse_mean"]

print(f"Delta MAE medio : {delta_mae:+.4f}")
print(f"Delta RMSE medio: {delta_rmse:+.4f}")

if delta_mae < 0 and delta_rmse < 0:
    print()
    print(">>> MIGLIORAMENTO CONFERMATO SU ENTRAMBE LE METRICHE <<<")
elif delta_mae < 0:
    print()
    print(">>> MAE MIGLIORA, RMSE PEGGIORA <<<")
elif delta_rmse < 0:
    print()
    print(">>> RMSE MIGLIORA, MAE PEGGIORA <<<")
else:
    print()
    print(">>> NESSUN MIGLIORAMENTO <<<")

# ------------------------------------------------------------
# SALVATAGGIO
# ------------------------------------------------------------

out = df[
    [
        "data",
        "casa",
        "ospite",
        "gol_casa_reali",
        "gol_ospite_reali",
        "gol_casa_attesi",
        "gol_ospite_attesi",
        "volume_tiri_casa",
        "volume_tiri_ospite",
    ]
].copy()

out["pred_volume_casa"] = ph_vol
out["pred_volume_ospite"] = pa_vol

out.to_csv(OUTPUT_FILE, index=False)

print()
print("=" * 70)
print("FILE SALVATO")
print("=" * 70)
print(OUTPUT_FILE)
print("Il modello principale NON è stato modificato.")
