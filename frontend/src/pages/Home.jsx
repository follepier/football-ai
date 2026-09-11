import React, { useState } from "react";
import "./Home.css";

function PercentCard({ label, value }) {
  return (
    <div className="prediction-card">
      <span>{label}</span>
      <strong>{value ?? 0}%</strong>
    </div>
  );
}

function MatchList({ matches, team }) {
  if (!matches?.length) return <p className="no-data">Nessun dato disponibile.</p>;

  return (
    <div className="matches-list">
      {matches.map((match, index) => (
        <div className="match-card" key={`${match.data}-${index}`}>
          <div className="match-header">
            <span>{match.data ? new Date(match.data).toLocaleDateString("it-IT") : "Data n/d"}</span>
            <span>{match.competizione || "Serie A"}</span>
          </div>
          <div className="match-main">
            <strong>
              {match.casa_trasferta === "casa"
                ? `${team} — ${match.avversario}`
                : `${match.avversario} — ${team}`}
            </strong>
            <b>{match.risultato || "-"}</b>
          </div>
          <div className="match-stats">
            <span>⚽ {match.gol_fatti ?? 0} fatti</span>
            <span>🛡️ {match.gol_subiti ?? 0} subiti</span>
            <span>🚩 {match.corner ?? 0} corner</span>
            <span>🟨 {match.ammonizioni ?? 0} ammonizioni</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function Home() {
  const [squadraCasa, setSquadraCasa] = useState("");
  const [squadraOspite, setSquadraOspite] = useState("");
  const [risultato, setRisultato] = useState(null);
  const [errore, setErrore] = useState("");
  const [caricamento, setCaricamento] = useState(false);

  async function analizzaPartita(event) {
    event?.preventDefault();
    setErrore("");
    setRisultato(null);

    if (!squadraCasa.trim() || !squadraOspite.trim()) {
      setErrore("Inserisci entrambe le squadre.");
      return;
    }

    setCaricamento(true);

    try {
      const params = new URLSearchParams({
        casa: squadraCasa.trim(),
        ospite: squadraOspite.trim(),
      });

      const response = await fetch(`/api/analyze?${params.toString()}`);
      const data = await response.json();

      if (!response.ok || data.status !== "success") {
        throw new Error("Risposta non valida dal backend");
      }

      setRisultato(data);
    } catch (error) {
      console.error(error);
      setErrore("Impossibile completare l'analisi. Verifica che il backend sia attivo.");
    } finally {
      setCaricamento(false);
    }
  }

  const analisi = risultato?.analisi;
  const unoXDue = analisi?.["1x2"] || {};
  const doppia = analisi?.doppia_chance || {};
  const over = analisi?.over_under || {};
  const golNoGol = analisi?.gol_no_gol || {};
  const volume = analisi?.volume_tiri || {};

  return (
    <div className="app">
      <header className="header">
        <div className="logo">
          <div className="logo-ball">⚽</div>
          <div>
            <h1>Football AI</h1>
            <p>Analisi statistica delle partite</p>
          </div>
        </div>
      </header>

      <main className="container">
        <section className="hero">
          <div className="hero-badge">⚡ AI MATCH ANALYZER</div>
          <h2>Analizza una partita</h2>
          <p>
            Inserisci le due squadre per ottenere indicatori statistici e probabilità.
            I risultati sono stime del modello, non certezze.
          </p>

          <form className="teams-form" onSubmit={analizzaPartita}>
            <div className="team-input">
              <label>🏠 Squadra casa</label>
              <input
                value={squadraCasa}
                onChange={(e) => setSquadraCasa(e.target.value)}
                placeholder="Es. Inter"
              />
            </div>
            <div className="vs">VS</div>
            <div className="team-input">
              <label>✈️ Squadra ospite</label>
              <input
                value={squadraOspite}
                onChange={(e) => setSquadraOspite(e.target.value)}
                placeholder="Es. Milan"
              />
            </div>
            <button className="analyze-button" type="submit" disabled={caricamento}>
              {caricamento ? "Analisi in corso..." : "Analizza partita →"}
            </button>
          </form>

          {errore && <div className="error">{errore}</div>}
        </section>

        {analisi && (
          <section className="results">
            <div className="match-title">
              <div>🏠 {analisi.casa}</div>
              <span>VS</span>
              <div>{analisi.ospite} ✈️</div>
            </div>

            <section className="section">
              <div className="section-title">
                <span>📊</span>
                <div><h3>Statistiche principali</h3><p>Indicatori prodotti dal modello</p></div>
              </div>
              <div className="stats-grid">
                <div className="stat-card highlight"><span>⚽ Gol attesi casa</span><strong>{analisi.gol_attesi_casa}</strong></div>
                <div className="stat-card highlight"><span>⚽ Gol attesi ospite</span><strong>{analisi.gol_attesi_ospite}</strong></div>
                <div className="stat-card main-highlight"><span>🎯 Gol attesi totali</span><strong>{analisi.gol_attesi_totali}</strong></div>
                <div className="stat-card"><span>🚩 Corner casa</span><strong>{analisi.corner_casa}</strong></div>
                <div className="stat-card"><span>🚩 Corner ospite</span><strong>{analisi.corner_ospite}</strong></div>
                <div className="stat-card"><span>🟨 Ammonizioni casa</span><strong>{analisi.ammonizioni_casa}</strong></div>
                <div className="stat-card"><span>🟨 Ammonizioni ospite</span><strong>{analisi.ammonizioni_ospite}</strong></div>
              </div>
            </section>

            <section className="section">
              <div className="section-title"><span>🎯</span><div><h3>1X2</h3><p>Probabilità degli esiti principali</p></div></div>
              <div className="prediction-grid">
                <PercentCard label="1 · Casa" value={unoXDue["1"]} />
                <PercentCard label="X · Pareggio" value={unoXDue.X} />
                <PercentCard label="2 · Ospite" value={unoXDue["2"]} />
              </div>
            </section>

            <section className="section">
              <div className="section-title"><span>🔄</span><div><h3>Doppia chance</h3><p>Combinazioni degli esiti</p></div></div>
              <div className="prediction-grid">
                <PercentCard label="1X" value={doppia["1X"]} />
                <PercentCard label="X2" value={doppia.X2} />
                <PercentCard label="12" value={doppia["12"]} />
              </div>
            </section>

            <section className="section">
              <div className="section-title"><span>⚽</span><div><h3>Over / Under</h3><p>Probabilità sui gol totali</p></div></div>
              <div className="ou-grid">
                {[["OVER 1.5", over.over_1_5],["UNDER 1.5", over.under_1_5],["OVER 2.5", over.over_2_5],["UNDER 2.5", over.under_2_5],["OVER 3.5", over.over_3_5],["UNDER 3.5", over.under_3_5]].map(([label,value]) => (
                  <div className="ou-card" key={label}><span>{label}</span><strong>{value ?? 0}%</strong></div>
                ))}
              </div>
            </section>

            <section className="section">
              <div className="section-title"><span>🥅</span><div><h3>Gol / No Gol</h3><p>Entrambe le squadre a segno</p></div></div>
              <div className="prediction-grid">
                <PercentCard label="GOL" value={golNoGol.gol} />
                <PercentCard label="NO GOL" value={golNoGol.no_gol} />
              </div>
            </section>

            <section className="section">
              <div className="section-title"><span>🎯</span><div><h3>Volume tiri</h3><p>Indicatore pre-partita disponibile nel modello</p></div></div>
              <div className="stats-grid">
                <div className="stat-card"><span>🏠 Volume casa</span><strong>{volume.casa ?? 0}</strong></div>
                <div className="stat-card"><span>✈️ Volume ospite</span><strong>{volume.ospite ?? 0}</strong></div>
                <div className="stat-card highlight"><span>↔️ Differenziale</span><strong>{volume.differenziale ?? 0}</strong></div>
              </div>
            </section>

            <section className="section">
              <div className="section-title"><span>🔢</span><div><h3>Risultati esatti più probabili</h3><p>Top 5 secondo la distribuzione del modello</p></div></div>
              <div className="exact-results">
                {(analisi.risultati_esatti || []).map((item, index) => (
                  <div className="exact-card" key={`${item.risultato}-${index}`}>
                    <span>#{index + 1}</span><strong>{item.risultato}</strong><b>{item.probabilita}%</b>
                  </div>
                ))}
              </div>
            </section>

            <section className="section">
              <div className="section-title"><span>🔥</span><div><h3>Forma recente</h3><p>Ultime partite disponibili</p></div></div>
              <div className="recent-grid">
                <div className="recent-team"><h4>🏠 {analisi.casa}</h4><MatchList matches={risultato.ultime_partite?.casa} team={analisi.casa} /></div>
                <div className="recent-team"><h4>✈️ {analisi.ospite}</h4><MatchList matches={risultato.ultime_partite?.ospite} team={analisi.ospite} /></div>
              </div>
            </section>
          </section>
        )}
      </main>

      <footer>
        <strong>Football AI</strong>
        <p>Indicatori statistici e probabilità · non costituiscono certezze di risultato</p>
      </footer>
    </div>
  );
}

export default Home;
