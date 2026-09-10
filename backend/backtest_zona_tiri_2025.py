import math
import os
import pandas as pd
import numpy as np

# ============================================================
# CONFIGURAZIONE
# ============================================================

SHOTS_PATH = "/tmp/understat_shots.parquet"
OUTPUT_PATH = "/workspaces/football-ai/data/serie_a_backtest_zona_tiri_2025.csv"

# Usiamo esclusivamente Serie A 2025/26
LEAGUE = "ITA"
SEASON = "2025"

# ============================================================
# FUNZIONI BASE
# ============================================================

def poisson_pmf(lam, gol):
    lam = max(float(lam), 0.0001)
    return math.exp(-lam) * (lam ** gol) / math.factorial(gol)


def stabilizza(media_squadra, numero_partite, media_campionato):
    numero_partite = max(int(numero_partite), 0)
    return (
        numero_partite * media_squadra
        + media_campionato
    ) / (numero_partite + 1)


def stima_baseline(
    casa_gf,
    casa_ga,
    ospite_gf,
    ospite_ga,
    media_campionato
):
    # Protezione contro la divisione per zero nelle
    # primissime partite della stagione.
    if media_campionato <= 0:
        media_campionato = 1.0

    def stabilizza(media_squadra):
        return (
            media_squadra + media_campionato
        ) / 2

    casa_attacco = stabilizza(casa_gf)
    casa_difesa = stabilizza(casa_ga)
    ospite_attacco = stabilizza(ospite_gf)
    ospite_difesa = stabilizza(ospite_ga)

    return (
        casa_attacco
        * ospite_difesa
        / media_campionato,
        ospite_attacco
        * casa_difesa
        / media_campionato
    )


def normalizza_nome(nome):
    nome = str(nome).strip()

    sostituzioni = {
        "AC Milan": "Milan",
        "Inter": "Inter",
        "Inter Milan": "Inter",
        "Parma Calcio 1913": "Parma",
    }

    return sostituzioni.get(nome, nome)


# ============================================================
# DEFINIZIONE ZONA DEL TIRO
# ============================================================
#
# Understat usa x/y normalizzati.
#
# x = distanza longitudinale dalla porta avversaria.
# y = posizione trasversale.
#
# Per evitare pesi arbitrari utilizziamo una definizione
# geometrica semplice:
#
# INSIDE BOX:
#   x >= 0.84
#   0.20 <= y <= 0.80
#
# OUTSIDE BOX:
#   tutti gli altri tiri.
#
# Non usiamo xG per questa variabile.
# ============================================================

def zona_tiro(x, y):
    x = float(x)
    y = float(y)

    if x >= 0.84 and 0.20 <= y <= 0.80:
        return "inside_box"

    return "outside_box"


# ============================================================
# CARICAMENTO DATI
# ============================================================

print("=" * 70)
print("BACKTEST ZONA TIRI - TEST SEPARATO")
print("=" * 70)

if not os.path.exists(SHOTS_PATH):
    print("ERRORE: file Understat non trovato:")
    print(SHOTS_PATH)
    raise SystemExit(1)

shots = pd.read_parquet(SHOTS_PATH)

print("\nTiri caricati:", len(shots))

# Solo Serie A
shots = shots[
    (shots["league_code"] == LEAGUE) &
    (shots["season"] == SEASON)
].copy()

shots["date"] = pd.to_datetime(shots["date"])
shots["date_day"] = shots["date"].dt.date

shots["h_team_norm"] = shots["h_team"].map(normalizza_nome)
shots["a_team_norm"] = shots["a_team"].map(normalizza_nome)

shots["zona"] = shots.apply(
    lambda r: zona_tiro(r["x"], r["y"]),
    axis=1
)

print("Tiri Serie A 2025/26:", len(shots))

# ============================================================
# COSTRUZIONE PARTITE
# ============================================================

matches = (
    shots[
        [
            "match_id",
            "date",
            "date_day",
            "h_team_norm",
            "a_team_norm",
            "h_goals",
            "a_goals",
        ]
    ]
    .drop_duplicates()
    .sort_values("date")
    .reset_index(drop=True)
)

print("Partite disponibili:", len(matches))

# ============================================================
# STATISTICHE STORICHE PER SQUADRA
# ============================================================

team_history = {}

def inizializza_squadra():
    return {
        "matches": 0,
        "goals_for": 0.0,
        "goals_against": 0.0,
        "shots_inside_for": 0.0,
        "shots_outside_for": 0.0,
        "shots_inside_against": 0.0,
        "shots_outside_against": 0.0,
    }


def get_team(team):
    if team not in team_history:
        team_history[team] = inizializza_squadra()
    return team_history[team]


# ============================================================
# STATISTICHE CAMPIONATO PROGRESSIVE
# ============================================================

league_goals = 0.0
league_matches = 0

# ============================================================
# RISULTATI
# ============================================================

results = []

# ============================================================
# WALK-FORWARD
# ============================================================

for _, match in matches.iterrows():

    match_id = match["match_id"]
    home = match["h_team_norm"]
    away = match["a_team_norm"]

    home_hist = get_team(home)
    away_hist = get_team(away)

    # --------------------------------------------------------
    # La previsione usa SOLO ciò che esiste PRIMA della partita
    # --------------------------------------------------------

    if league_matches == 0:
        media_campionato = 1.5
    else:
        media_campionato = league_goals / (2 * league_matches)

    # Evitiamo di usare squadre senza storico.
    # Per le prime partite utilizziamo la media campionato.
    home_matches = home_hist["matches"]
    away_matches = away_hist["matches"]

    if home_matches > 0:
        home_gf = home_hist["goals_for"] / home_matches
        home_ga = home_hist["goals_against"] / home_matches
    else:
        home_gf = media_campionato
        home_ga = media_campionato

    if away_matches > 0:
        away_gf = away_hist["goals_for"] / away_matches
        away_ga = media_campionato
    else:
        away_gf = media_campionato
        away_ga = media_campionato

    # --------------------------------------------------------
    # BASELINE
    # --------------------------------------------------------

    base_home, base_away = stima_baseline(
        home_gf,
        home_ga,
        away_gf,
        away_ga,
        media_campionato,
    )

    # --------------------------------------------------------
    # ZONA TIRI STORICA
    # --------------------------------------------------------

    if home_matches > 0:
        home_inside_for = (
            home_hist["shots_inside_for"] / home_matches
        )
        home_outside_for = (
            home_hist["shots_outside_for"] / home_matches
        )
        home_inside_against = (
            home_hist["shots_inside_against"] / home_matches
        )
        home_outside_against = (
            home_hist["shots_outside_against"] / home_matches
        )
    else:
        home_inside_for = 0.0
        home_outside_for = 0.0
        home_inside_against = 0.0
        home_outside_against = 0.0

    if away_matches > 0:
        away_inside_for = (
            away_hist["shots_inside_for"] / away_matches
        )
        away_outside_for = (
            away_hist["shots_outside_for"] / away_matches
        )
        away_inside_against = (
            away_hist["shots_inside_against"] / away_matches
        )
        away_outside_against = (
            away_hist["shots_outside_against"] / away_matches
        )
    else:
        away_inside_for = 0.0
        away_outside_for = 0.0
        away_inside_against = 0.0
        away_outside_against = 0.0

    # --------------------------------------------------------
    # VARIABILI DI ZONA
    # --------------------------------------------------------
    #
    # Produzione prevista dentro area:
    # media tra:
    #   - produzione interna della squadra
    #   - concessione interna dell'avversaria
    #
    # Stesso principio per fuori area.
    #
    # Non vengono assegnati pesi arbitrari.
    # --------------------------------------------------------

    expected_home_inside = (
        home_inside_for + away_inside_against
    ) / 2

    expected_away_inside = (
        away_inside_for + home_inside_against
    ) / 2

    expected_home_outside = (
        home_outside_for + away_outside_against
    ) / 2

    expected_away_outside = (
        away_outside_for + home_outside_against
    ) / 2

    # --------------------------------------------------------
    # Aggiornamento della cronologia CON LA PARTITA CORRENTE
    # avviene SOLO DOPO aver prodotto la previsione.
    # --------------------------------------------------------

    match_shots = shots[shots["match_id"] == match_id]

    home_shots = match_shots[
        match_shots["h_a"] == "h"
    ]

    away_shots = match_shots[
        match_shots["h_a"] == "a"
    ]

    home_inside = int(
        (home_shots["zona"] == "inside_box").sum()
    )

    home_outside = int(
        (home_shots["zona"] == "outside_box").sum()
    )

    away_inside = int(
        (away_shots["zona"] == "inside_box").sum()
    )

    away_outside = int(
        (away_shots["zona"] == "outside_box").sum()
    )

    # Salviamo il risultato
    results.append({
        "match_id": match_id,
        "data": match["date"],
        "casa": home,
        "ospite": away,
        "gol_casa_reali": float(match["h_goals"]),
        "gol_ospite_reali": float(match["a_goals"]),

        "gol_casa_baseline": base_home,
        "gol_ospite_baseline": base_away,

        "tiri_dentro_casa_pre": home_inside_for,
        "tiri_fuori_casa_pre": home_outside_for,
        "tiri_dentro_casa_concessi_pre": home_inside_against,
        "tiri_fuori_casa_concessi_pre": home_outside_against,

        "tiri_dentro_ospite_pre": away_inside_for,
        "tiri_fuori_ospite_pre": away_outside_for,
        "tiri_dentro_ospite_concessi_pre": away_inside_against,
        "tiri_fuori_ospite_concessi_pre": away_outside_against,

        "expected_tiri_dentro_casa": expected_home_inside,
        "expected_tiri_dentro_ospite": expected_away_inside,
        "expected_tiri_fuori_casa": expected_home_outside,
        "expected_tiri_fuori_ospite": expected_away_outside,

        "tiri_dentro_casa_reali": home_inside,
        "tiri_fuori_casa_reali": home_outside,
        "tiri_dentro_ospite_reali": away_inside,
        "tiri_fuori_ospite_reali": away_outside,
    })

    # --------------------------------------------------------
    # AGGIORNAMENTO STORICO
    # --------------------------------------------------------

    home_hist["matches"] += 1
    home_hist["goals_for"] += float(match["h_goals"])
    home_hist["goals_against"] += float(match["a_goals"])

    home_hist["shots_inside_for"] += home_inside
    home_hist["shots_outside_for"] += home_outside
    home_hist["shots_inside_against"] += away_inside
    home_hist["shots_outside_against"] += away_outside

    away_hist["matches"] += 1
    away_hist["goals_for"] += float(match["a_goals"])
    away_hist["goals_against"] += float(match["h_goals"])

    away_hist["shots_inside_for"] += away_inside
    away_hist["shots_outside_for"] += away_outside
    away_hist["shots_inside_against"] += home_inside
    away_hist["shots_outside_against"] += home_outside

    league_goals += float(match["h_goals"])
    league_goals += float(match["a_goals"])
    league_matches += 1


# ============================================================
# DATAFRAME RISULTATI
# ============================================================

result_df = pd.DataFrame(results)

# ------------------------------------------------------------
# Evitiamo di valutare le prime partite senza storico.
# Servono almeno 3 partite precedenti per entrambe le squadre.
# ------------------------------------------------------------

valid = []

for _, row in result_df.iterrows():
    # Ricostruiamo il minimo storico dalla disponibilità delle
    # variabili pre-partita.
    if (
        row["tiri_dentro_casa_pre"]
        + row["tiri_fuori_casa_pre"]
        + row["tiri_dentro_casa_concessi_pre"]
        + row["tiri_fuori_casa_concessi_pre"]
        > 0
        and
        row["tiri_dentro_ospite_pre"]
        + row["tiri_fuori_ospite_pre"]
        + row["tiri_dentro_ospite_concessi_pre"]
        + row["tiri_fuori_ospite_concessi_pre"]
        > 0
    ):
        valid.append(True)
    else:
        valid.append(False)

result_df["valido"] = valid

test = result_df[result_df["valido"]].copy()

# ============================================================
# METRICHE BASELINE
# ============================================================

base_mae_home = np.mean(
    np.abs(
        test["gol_casa_reali"]
        - test["gol_casa_baseline"]
    )
)

base_mae_away = np.mean(
    np.abs(
        test["gol_ospite_reali"]
        - test["gol_ospite_baseline"]
    )
)

base_rmse_home = np.sqrt(
    np.mean(
        (
            test["gol_casa_reali"]
            - test["gol_casa_baseline"]
        ) ** 2
    )
)

base_rmse_away = np.sqrt(
    np.mean(
        (
            test["gol_ospite_reali"]
            - test["gol_ospite_baseline"]
        ) ** 2
    )
)

# ============================================================
# TEST CORREZIONE LINEARE ZONA TIRI
# ============================================================
#
# Non usiamo pesi scelti manualmente.
# La correzione viene stimata esclusivamente sui dati storici
# precedenti alla partita tramite regressione expanding.
#
# Testiamo separatamente:
# 1. tiri dentro area
# 2. tiri fuori area
# 3. dentro + fuori
#
# La regressione per ogni partita usa solo le righe precedenti.
# ============================================================

from sklearn.linear_model import LinearRegression

def expanding_prediction(test_df, target, features):

    predictions = []

    for i in range(len(test_df)):

        train = test_df.iloc[:i]

        if len(train) < 5:
            predictions.append(
                test_df.iloc[i]["gol_casa_baseline"]
                if target == "home"
                else test_df.iloc[i]["gol_ospite_baseline"]
            )
            continue

        X_train = train[features].fillna(0)

        if target == "home":
            residual = (
                train["gol_casa_reali"]
                - train["gol_casa_baseline"]
            )
            baseline_value = test_df.iloc[i]["gol_casa_baseline"]
        else:
            residual = (
                train["gol_ospite_reali"]
                - train["gol_ospite_baseline"]
            )
            baseline_value = test_df.iloc[i]["gol_ospite_baseline"]

        model = LinearRegression()
        model.fit(X_train, residual)

        X_test = test_df.iloc[[i]][features].fillna(0)

        correction = model.predict(X_test)[0]

        predictions.append(
            max(0.01, baseline_value + correction)
        )

    return predictions


feature_sets = {
    "dentro_area": [
        "expected_tiri_dentro_casa",
        "expected_tiri_dentro_ospite",
    ],
    "fuori_area": [
        "expected_tiri_fuori_casa",
        "expected_tiri_fuori_ospite",
    ],
    "dentro_fuori": [
        "expected_tiri_dentro_casa",
        "expected_tiri_dentro_ospite",
        "expected_tiri_fuori_casa",
        "expected_tiri_fuori_ospite",
    ],
}

summary = []

for nome, features in feature_sets.items():

    pred_home = expanding_prediction(
        test,
        "home",
        features
    )

    pred_away = expanding_prediction(
        test,
        "away",
        features
    )

    pred_home = np.array(pred_home)
    pred_away = np.array(pred_away)

    mae_home = np.mean(
        np.abs(test["gol_casa_reali"] - pred_home)
    )

    mae_away = np.mean(
        np.abs(test["gol_ospite_reali"] - pred_away)
    )

    rmse_home = np.sqrt(
        np.mean(
            (test["gol_casa_reali"] - pred_home) ** 2
        )
    )

    rmse_away = np.sqrt(
        np.mean(
            (test["gol_ospite_reali"] - pred_away) ** 2
        )
    )

    summary.append({
        "modello": nome,
        "partite_test": len(test),
        "mae_home": mae_home,
        "mae_away": mae_away,
        "mae_mean": (mae_home + mae_away) / 2,
        "rmse_home": rmse_home,
        "rmse_away": rmse_away,
        "rmse_mean": (rmse_home + rmse_away) / 2,
        "delta_mae_vs_baseline": (
            (mae_home + mae_away) / 2
            - (base_mae_home + base_mae_away) / 2
        ),
        "delta_rmse_vs_baseline": (
            (rmse_home + rmse_away) / 2
            - (base_rmse_home + base_rmse_away) / 2
        ),
    })

# ============================================================
# STAMPA RISULTATI
# ============================================================

print("\n" + "=" * 70)
print("BASELINE")
print("=" * 70)

print(f"Partite test: {len(test)}")
print(f"MAE casa:     {base_mae_home:.4f}")
print(f"MAE ospite:   {base_mae_away:.4f}")
print(
    f"MAE medio:    {(base_mae_home + base_mae_away) / 2:.4f}"
)
print(f"RMSE casa:    {base_rmse_home:.4f}")
print(f"RMSE ospite:  {base_rmse_away:.4f}")
print(
    f"RMSE medio:   {(base_rmse_home + base_rmse_away) / 2:.4f}"
)

print("\n" + "=" * 70)
print("TEST ZONA TIRI")
print("=" * 70)

summary_df = pd.DataFrame(summary)

print(
    summary_df.to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)

# ============================================================
# SALVATAGGIO
# ============================================================

result_df.to_csv(
    OUTPUT_PATH,
    index=False
)

print("\n" + "=" * 70)
print("FILE SALVATO")
print("=" * 70)
print(OUTPUT_PATH)
print("Il modello principale NON è stato modificato.")
