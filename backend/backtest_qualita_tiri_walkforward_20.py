import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error

FEATURES = "data/serie_a_features.csv"
DATASET = "data/serie_a_dataset.csv"


def stabilizza(media_squadra, numero_partite, media_campionato):
    numero_partite = max(numero_partite, 0)
    if media_campionato <= 0:
        media_campionato = 1.0

    return (
        numero_partite * media_squadra + media_campionato
    ) / (numero_partite + 1)


def stima_baseline(
    casa_gol_fatti,
    casa_gol_subiti,
    ospite_gol_fatti,
    ospite_gol_subiti,
    media_campionato,
    n_casa=1,
    n_ospite=1
):
    if media_campionato <= 0:
        media_campionato = 1.0

    casa_attacco = stabilizza(
        casa_gol_fatti, n_casa, media_campionato
    )
    casa_difesa = stabilizza(
        casa_gol_subiti, n_casa, media_campionato
    )
    ospite_attacco = stabilizza(
        ospite_gol_fatti, n_ospite, media_campionato
    )
    ospite_difesa = stabilizza(
        ospite_gol_subiti, n_ospite, media_campionato
    )

    gol_casa = (
        casa_attacco * ospite_difesa / media_campionato
    )
    gol_ospite = (
        ospite_attacco * casa_difesa / media_campionato
    )

    return gol_casa, gol_ospite


def safe_ratio(a, b):
    if b == 0 or pd.isna(b):
        return 0.0
    return a / b


features = pd.read_csv(FEATURES)
dataset = pd.read_csv(DATASET)

features["data"] = pd.to_datetime(features["data"])
dataset["data"] = pd.to_datetime(dataset["data"])

# serie_a_features.csv non contiene fixture_id:
# le features sono già costruite nello stesso ordine temporale
# del dataset. Usiamo quindi direttamente le righe corrispondenti.
features = features.sort_values("data").reset_index(drop=True)
dataset = dataset.sort_values("data").reset_index(drop=True)

if len(features) != len(dataset):
    raise ValueError(
        f"Numero righe diverso: features={len(features)}, dataset={len(dataset)}"
    )

df = features.copy()
df["gol_casa"] = dataset["gol_casa"].to_numpy()
df["gol_ospite"] = dataset["gol_ospite"].to_numpy()

df = df.sort_values("data").reset_index(drop=True)

# stesso benchmark ufficiale: ultime 20 partite
test = df.tail(20).copy()

# media campionato calcolata solo progressivamente
results = {
    "baseline": [],
    "precisione": [],
    "pericolosita": [],
    "xg_per_tiro": [],
    "precisione_pericolosita": [],
    "qualita_completa": []
}

y_casa = test["gol_casa"].to_numpy()
y_ospite = test["gol_ospite"].to_numpy()


for i in range(len(test)):

    row = test.iloc[i]

    # dati disponibili PRIMA della partita
    train = df.iloc[:len(df) - 20 + i]

    if len(train) == 0:
        continue

    # Media campionato coerente con il benchmark ufficiale:
    # viene calcolata sui dati disponibili prima della partita.
    media_campionato = (
        train["gol_casa"].sum() + train["gol_ospite"].sum()
    ) / (2 * len(train))

    base_casa, base_ospite = stima_baseline(
        row["casa_gol_fatti_totale_pre"],
        row["casa_gol_subiti_totale_pre"],
        row["ospite_gol_fatti_totale_pre"],
        row["ospite_gol_subiti_totale_pre"],
        media_campionato
    )

    results["baseline"].append(
        (base_casa, base_ospite)
    )

    # -----------------------------
    # VARIABILI PRE-MATCH
    # -----------------------------

    # Tiri totali
    hc = (
        row["casa_tiri_in_porta_totale_pre"]
        + row["casa_tiri_fuori_totale_pre"]
    )
    ac = (
        row["ospite_tiri_in_porta_totale_pre"]
        + row["ospite_tiri_fuori_totale_pre"]
    )

    # Precisione dei tiri
    precisione_casa = safe_ratio(
        row["casa_tiri_in_porta_totale_pre"], hc
    )
    precisione_ospite = safe_ratio(
        row["ospite_tiri_in_porta_totale_pre"], ac
    )

    # Pericolosità dell'attacco
    pericolosita_casa = safe_ratio(
        row["casa_attacchi_pericolosi_totale_pre"],
        row["casa_attacchi_totale_pre"]
    )
    pericolosita_ospite = safe_ratio(
        row["ospite_attacchi_pericolosi_totale_pre"],
        row["ospite_attacchi_totale_pre"]
    )

    # xG per tiro
    xg_per_tiro_casa = safe_ratio(
        row["casa_xg_fatti_totale_pre"], hc
    )
    xg_per_tiro_ospite = safe_ratio(
        row["ospite_xg_fatti_totale_pre"], ac
    )

    features_row = {
        "precisione": [
            precisione_casa,
            precisione_ospite
        ],
        "pericolosita": [
            pericolosita_casa,
            pericolosita_ospite
        ],
        "xg_per_tiro": [
            xg_per_tiro_casa,
            xg_per_tiro_ospite
        ],
        "precisione_pericolosita": [
            precisione_casa,
            precisione_ospite,
            pericolosita_casa,
            pericolosita_ospite
        ],
        "qualita_completa": [
            precisione_casa,
            precisione_ospite,
            pericolosita_casa,
            pericolosita_ospite,
            xg_per_tiro_casa,
            xg_per_tiro_ospite
        ]
    }

    # Per evitare di usare il futuro:
    # la correzione viene addestrata solamente sulle partite precedenti.
    historical = df.iloc[:len(df) - 20 + i].copy()

    if len(historical) < 5:
        for key in features_row:
            results[key].append((base_casa, base_ospite))
        continue

    # Costruiamo i residui storici della baseline
    X_hist = []
    resid_home = []
    resid_away = []

    for j in range(len(historical)):

        h = historical.iloc[j]

        # media disponibile prima della partita storica
        hist_before = historical.iloc[:j]

        if len(hist_before) == 0:
            continue

        media_hist = (
            hist_before["gol_casa"].mean()
            + hist_before["gol_ospite"].mean()
        ) / 2

        bh, ba = stima_baseline(
            h["casa_gol_fatti_totale_pre"],
            h["casa_gol_subiti_totale_pre"],
            h["ospite_gol_fatti_totale_pre"],
            h["ospite_gol_subiti_totale_pre"],
            media_hist
        )

        ht = (
            h["casa_tiri_in_porta_totale_pre"]
            + h["casa_tiri_fuori_totale_pre"]
        )
        at = (
            h["ospite_tiri_in_porta_totale_pre"]
            + h["ospite_tiri_fuori_totale_pre"]
        )

        pc_h = safe_ratio(
            h["casa_tiri_in_porta_totale_pre"], ht
        )
        pc_a = safe_ratio(
            h["ospite_tiri_in_porta_totale_pre"], at
        )

        pd_h = safe_ratio(
            h["casa_attacchi_pericolosi_totale_pre"],
            h["casa_attacchi_totale_pre"]
        )
        pd_a = safe_ratio(
            h["ospite_attacchi_pericolosi_totale_pre"],
            h["ospite_attacchi_totale_pre"]
        )

        xpt_h = safe_ratio(
            h["casa_xg_fatti_totale_pre"], ht
        )
        xpt_a = safe_ratio(
            h["ospite_xg_fatti_totale_pre"], at
        )

        X_hist.append([
            pc_h, pc_a,
            pd_h, pd_a,
            xpt_h, xpt_a
        ])

        resid_home.append(h["gol_casa"] - bh)
        resid_away.append(h["gol_ospite"] - ba)

    if len(X_hist) < 5:
        for key in features_row:
            results[key].append((base_casa, base_ospite))
        continue

    X_hist = np.array(X_hist, dtype=float)
    resid_home = np.array(resid_home, dtype=float)
    resid_away = np.array(resid_away, dtype=float)

    # Eliminiamo esclusivamente le osservazioni storiche incomplete.
    # Non imputiamo valori mancanti e non introduciamo dati artificiali.
    valid = (
        np.isfinite(X_hist).all(axis=1)
        & np.isfinite(resid_home)
        & np.isfinite(resid_away)
    )

    X_hist = X_hist[valid]
    resid_home = resid_home[valid]
    resid_away = resid_away[valid]

    if len(X_hist) < 5:
        for key in features_row:
            results[key].append((base_casa, base_ospite))
        continue

    # Modelli separati per casa e trasferta
    for key, vals in features_row.items():

        if key == "precisione":
            idx = [0, 1]
        elif key == "pericolosita":
            idx = [2, 3]
        elif key == "xg_per_tiro":
            idx = [4, 5]
        elif key == "precisione_pericolosita":
            idx = [0, 1, 2, 3]
        else:
            idx = [0, 1, 2, 3, 4, 5]

        # Per le combinazioni, testiamo solo il blocco richiesto.
        X = X_hist[:, idx]

        # target separati
        model_home = LinearRegression()
        model_away = LinearRegression()

        model_home.fit(X, resid_home)
        model_away.fit(X, resid_away)

        if key == "precisione":
            x_now = np.array([
                precisione_casa,
                precisione_ospite
            ])
        elif key == "pericolosita":
            x_now = np.array([
                pericolosita_casa,
                pericolosita_ospite
            ])
        elif key == "xg_per_tiro":
            x_now = np.array([
                xg_per_tiro_casa,
                xg_per_tiro_ospite
            ])
        elif key == "precisione_pericolosita":
            x_now = np.array([
                precisione_casa,
                precisione_ospite,
                pericolosita_casa,
                pericolosita_ospite
            ])
        else:
            x_now = np.array([
                precisione_casa,
                precisione_ospite,
                pericolosita_casa,
                pericolosita_ospite,
                xg_per_tiro_casa,
                xg_per_tiro_ospite
            ])

        pred_h = base_casa + model_home.predict(
            x_now.reshape(1, -1)
        )[0]

        pred_a = base_ospite + model_away.predict(
            x_now.reshape(1, -1)
        )[0]

        # sicurezza: niente gol attesi negativi
        pred_h = max(0.0, pred_h)
        pred_a = max(0.0, pred_a)

        results[key].append((pred_h, pred_a))


def metriche(nome, preds):
    ph = np.array([x[0] for x in preds])
    pa = np.array([x[1] for x in preds])

    mae_h = mean_absolute_error(y_casa, ph)
    mae_a = mean_absolute_error(y_ospite, pa)

    rmse_h = np.sqrt(mean_squared_error(y_casa, ph))
    rmse_a = np.sqrt(mean_squared_error(y_ospite, pa))

    mae = (mae_h + mae_a) / 2
    rmse = (rmse_h + rmse_a) / 2

    return {
        "variabile": nome,
        "mae": mae,
        "rmse": rmse
    }


output = []

for nome, preds in results.items():
    if len(preds) == 20:
        output.append(metriche(nome, preds))

risultati = pd.DataFrame(output)

baseline_mae = risultati.loc[
    risultati["variabile"] == "baseline", "mae"
].iloc[0]

baseline_rmse = risultati.loc[
    risultati["variabile"] == "baseline", "rmse"
].iloc[0]

risultati["delta_mae"] = risultati["mae"] - baseline_mae
risultati["delta_rmse"] = risultati["rmse"] - baseline_rmse

print("\n==========================================")
print(" BACKTEST QUALITA' TIRI - WALK FORWARD")
print("==========================================\n")

for _, r in risultati.iterrows():
    print(
        f"{r['variabile']:28s} "
        f"MAE={r['mae']:.4f} "
        f"RMSE={r['rmse']:.4f} "
        f"dMAE={r['delta_mae']:+.4f} "
        f"dRMSE={r['delta_rmse']:+.4f}"
    )

print("\n------------------------------------------")
print(f"BASELINE MAE  = {baseline_mae:.4f}")
print(f"BASELINE RMSE = {baseline_rmse:.4f}")
print("------------------------------------------")

migliorano_entrambi = risultati[
    (risultati["delta_mae"] < 0) &
    (risultati["delta_rmse"] < 0)
]

print("\nVariabili che migliorano CONTEMPORANEAMENTE MAE e RMSE:")

if migliorano_entrambi.empty:
    print("NESSUNA")
else:
    print(
        migliorano_entrambi[
            ["variabile", "mae", "rmse", "delta_mae", "delta_rmse"]
        ].to_string(index=False)
    )

risultati.to_csv(
    "data/serie_a_backtest_qualita_tiri_walkforward_20.csv",
    index=False
)

print(
    "\nRisultati salvati in "
    "data/serie_a_backtest_qualita_tiri_walkforward_20.csv"
)
