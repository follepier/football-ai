import React, { useState } from "react";
import "./Home.css";

function Home() {
  const [squadraCasa, setSquadraCasa] = useState("");
  const [squadraOspite, setSquadraOspite] = useState("");
  const [risultato, setRisultato] = useState(null);
  const [errore, setErrore] = useState("");
  const [caricamento, setCaricamento] = useState(false);

  async function analizzaPartita() {
    setErrore("");
    setRisultato(null);

    if (!squadraCasa.trim() || !squadraOspite.trim()) {
      setErrore("Inserisci entrambe le squadre.");
      return;
    }

    setCaricamento(true);

    try {
      const url =
        `/api/analyze?casa=${encodeURIComponent(squadraCasa.trim())}` +
        `&ospite=${encodeURIComponent(squadraOspite.trim())}`;

      const response = await fetch(url);

      if (!response.ok) {
        throw new Error("Errore nella risposta del server");
      }

      const data = await response.json();
      setRisultato(data);
    } catch (error) {
      console.error(error);
      setErrore("Errore nel collegamento al backend.");
    } finally {
      setCaricamento(false);
    }
  }

  function mostraPartite(partite, squadraAnalizzata) {
  if (!partite || partite.length === 0) {
    return <p className="no-data">Nessun dato disponibile.</p>;
  }

  return (
    <div className="matches-list">
      {partite.map((partita, index) => (
        <div className="match-card" key={index}>
          <div className="match-number">
            PARTITA {index + 1}
          </div>

          <div className="match-header">
            <small className="match-date">
              {partita.data
                ? new Date(
                    partita.data.replace("+00:00", "Z")
                  ).toLocaleDateString("it-IT")
                : "Data non disponibile"}
            </small>

            <small className="match-competition">
              {partita.competizione}
            </small>
          </div>

          <div className="match-main">
            <strong className="match-opponent">
              {partita.casa_trasferta === "casa"
                ? `${squadraAnalizzata.charAt(0).toUpperCase()}${squadraAnalizzata.slice(1)} — ${partita.avversario}`
                : `${partita.avversario} — ${squadraAnalizzata.charAt(0).toUpperCase()}${squadraAnalizzata.slice(1)}`}
            </strong>

            <span className="match-result">
              {partita.risultato}
            </span>
          </div>

          <div className="match-location">
            {partita.casa_trasferta === "casa"
              ? "🏠 Casa"
              : "✈️ Trasferta"}
          </div>

          <div className="match-stats">
            <span>⚽ {partita.gol_fatti} fatti</span>
            <span>🛡️ {partita.gol_subiti} subiti</span>
            <span>🚩 {partita.corner} corner</span>
            <span>🟨 {partita.ammonizioni} ammonizioni</span>
          </div>
        </div>
      ))}
    </div>
  );
}

  const analisi = risultato?.analisi;

  return (
    <div className="app">

      <header className="header">
        <div className="logo">
          <div className="logo-ball">⚽</div>
          <div>
            <h1>Football AI</h1>
            <p>Analisi intelligente delle partite</p>
          </div>
        </div>
      </header>

      <main className="container">

        <section className="hero">
          <div className="hero-badge">
            ⚡ AI MATCH ANALYZER
          </div>

          <h2>Analizza una partita</h2>

          <p>
            Inserisci le due squadre per ottenere statistiche,
            probabilità e risultati più probabili.
          </p>

          <div className="teams-form">

            <div className="team-input">
              <label>🏠 Squadra casa</label>

              <input
                type="text"
                value={squadraCasa}
                onChange={(e) => setSquadraCasa(e.target.value)}
                placeholder="Es. Inter"
              />
            </div>

            <div className="vs">
              VS
            </div>

            <div className="team-input">
              <label>✈️ Squadra ospite</label>

              <input
                type="text"
                value={squadraOspite}
                onChange={(e) => setSquadraOspite(e.target.value)}
                placeholder="Es. Milan"
              />
            </div>

          </div>

          <button
            className="analyze-button"
            onClick={analizzaPartita}
            disabled={caricamento}
          >
            {caricamento ? "Analisi in corso..." : "Analizza partita →"}
          </button>

          {errore && (
            <div className="error">
              {errore}
            </div>
          )}
        </section>


        {analisi && (
          <section className="results">

            <div className="match-title">
              <div className="team-name">
                <span>🏠</span>
                {analisi.casa}
              </div>

              <div className="match-vs">
                VS
              </div>

              <div className="team-name">
                {analisi.ospite}
                <span>✈️</span>
              </div>
            </div>


            <section className="section">

              <div className="section-title">
                <span>📊</span>
                <div>
                  <h3>Statistiche principali</h3>
                  <p>Indicatori calcolati dal modello</p>
                </div>
              </div>

              <div className="stats-grid">

                <div className="stat-card highlight">
                  <span className="stat-icon">⚽</span>
                  <span className="stat-label">
                    Gol attesi casa
                  </span>
                  <strong>
                    {analisi.gol_attesi_casa}
                  </strong>
                </div>

                <div className="stat-card highlight">
                  <span className="stat-icon">⚽</span>
                  <span className="stat-label">
                    Gol attesi ospite
                  </span>
                  <strong>
                    {analisi.gol_attesi_ospite}
                  </strong>
                </div>

                <div className="stat-card main-highlight">
                  <span className="stat-icon">🎯</span>
                  <span className="stat-label">
                    Gol attesi totali
                  </span>
                  <strong>
                    {analisi.gol_attesi_totali}
                  </strong>
                </div>

                <div className="stat-card">
                  <span className="stat-icon">🚩</span>
                  <span className="stat-label">
                    Corner casa
                  </span>
                  <strong>
                    {analisi.corner_casa}
                  </strong>
                </div>

                <div className="stat-card">
                  <span className="stat-icon">🚩</span>
                  <span className="stat-label">
                    Corner ospite
                  </span>
                  <strong>
                    {analisi.corner_ospite}
                  </strong>
                </div>

                <div className="stat-card">
                  <span className="stat-icon">🟨</span>
                  <span className="stat-label">
                    Ammonizioni casa
                  </span>
                  <strong>
                    {analisi.ammonizioni_casa}
                  </strong>
                </div>

                <div className="stat-card">
                  <span className="stat-icon">🟨</span>
                  <span className="stat-label">
                    Ammonizioni ospite
                  </span>
                  <strong>
                    {analisi.ammonizioni_ospite}
                  </strong>
                </div>

              </div>
            </section>


            <section className="section">

              <div className="section-title">
                <span>🎯</span>
                <div>
                  <h3>Pronostico 1X2</h3>
                  <p>Probabilità degli esiti principali</p>
                </div>
              </div>

              <div className="prediction-grid">

                <div className="prediction-card">
                  <span>1</span>
                  <strong>{analisi["1x2"]["1"]}%</strong>
                  <small>Vittoria casa</small>
                </div>

                <div className="prediction-card">
                  <span>X</span>
                  <strong>{analisi["1x2"]["X"]}%</strong>
                  <small>Pareggio</small>
                </div>

                <div className="prediction-card">
                  <span>2</span>
                  <strong>{analisi["1x2"]["2"]}%</strong>
                  <small>Vittoria ospite</small>
                </div>

              </div>
            </section>


            <section className="section">

              <div className="section-title">
                <span>🔄</span>
                <div>
                  <h3>Doppia chance</h3>
                  <p>Probabilità delle combinazioni</p>
                </div>
              </div>

              <div className="prediction-grid">

                <div className="prediction-card">
                  <span>1X</span>
                  <strong>{analisi.doppia_chance["1X"]}%</strong>
                  <small>Casa o pareggio</small>
                </div>

                <div className="prediction-card">
                  <span>X2</span>
                  <strong>{analisi.doppia_chance["X2"]}%</strong>
                  <small>Pareggio o ospite</small>
                </div>

                <div className="prediction-card">
                  <span>12</span>
                  <strong>{analisi.doppia_chance["12"]}%</strong>
                  <small>Niente pareggio</small>
                </div>

              </div>
            </section>


            <section className="section">

              <div className="section-title">
                <span>⚽</span>
                <div>
                  <h3>Over / Under</h3>
                  <p>Probabilità sui gol totali</p>
                </div>
              </div>

              <div className="ou-grid">

                <div className="ou-card">
                  <span>OVER 1.5</span>
                  <strong>
                    {analisi.over_under.over_1_5}%
                  </strong>
                </div>

                <div className="ou-card">
                  <span>UNDER 1.5</span>
                  <strong>
                    {analisi.over_under.under_1_5}%
                  </strong>
                </div>

                <div className="ou-card">
                  <span>OVER 2.5</span>
                  <strong>
                    {analisi.over_under.over_2_5}%
                  </strong>
                </div>

                <div className="ou-card">
                  <span>UNDER 2.5</span>
                  <strong>
                    {analisi.over_under.under_2_5}%
                  </strong>
                </div>

                <div className="ou-card">
                  <span>OVER 3.5</span>
                  <strong>
                    {analisi.over_under.over_3_5}%
                  </strong>
                </div>

                <div className="ou-card">
                  <span>UNDER 3.5</span>
                  <strong>
                    {analisi.over_under.under_3_5}%
                  </strong>
                </div>

              </div>
            </section>


            <section className="section">

              <div className="section-title">
                <span>🥅</span>
                <div>
                  <h3>Gol / No Gol</h3>
                  <p>Probabilità che entrambe segnino</p>
                </div>
              </div>

              <div className="goal-grid">

                <div className="goal-card">
                  <span>GOL</span>
                  <strong>
                    {analisi.gol_no_gol.gol}%
                  </strong>
                </div>

                <div className="goal-card">
                  <span>NO GOL</span>
                  <strong>
                    {analisi.gol_no_gol.no_gol}%
                  </strong>
                </div>

              </div>
            </section>


            <section className="section">

              <div className="section-title">
                <span>🔢</span>
                <div>
                  <h3>Risultati esatti più probabili</h3>
                  <p>Top 5 risultati generati dal modello</p>
                </div>
              </div>

              <div className="exact-results">

                {analisi.risultati_esatti.map(
                  (item, index) => (
                    <div
                      className="exact-card"
                      key={index}
                    >
                      <div className="rank">
                        #{index + 1}
                      </div>

                      <div className="exact-score">
                        {item.risultato}
                      </div>

                      <div className="exact-probability">
                        {item.probabilita}%
                      </div>
                    </div>
                  )
                )}

              </div>
            </section>


            <section className="section">

              <div className="section-title">
                <span>🔥</span>
                <div>
                  <h3>Forma recente</h3>
                  <p>Forma recente delle due squadre</p>
                </div>
              </div>

              <div className="recent-grid">

                <div className="recent-team">
                  <h4>🏠 {analisi.casa}</h4>
                  {mostraPartite(
                    risultato.ultime_partite?.casa,
                    analisi.casa
                  )}
                </div>

                <div className="recent-team">
                  <h4>✈️ {analisi.ospite}</h4>
                  {mostraPartite(
                    risultato.ultime_partite?.ospite,
                    analisi.ospite
                  )}
                </div>

              </div>
            </section>

          </section>
        )}
      </main>


      <footer>
        <strong>Football AI</strong>
        <p>
          Analisi statistica intelligente delle partite
        </p>
      </footer>

    </div>
  );
}

export default Home;
