import React, { useEffect, useState } from "react";
import "./Home.css";
import "./MultiLeague.css";
import UpcomingFixtures from "./UpcomingFixtures";
import AdvancedMetrics from "./AdvancedMetrics";

const COMPETIZIONI_FALLBACK = [
  { slug: "serie-a", name: "Serie A", country: "Italia", model_validated: true },
  { slug: "premier-league", name: "Premier League", country: "Inghilterra", model_validated: true },
  { slug: "la-liga", name: "La Liga", country: "Spagna", model_validated: true },
  { slug: "bundesliga", name: "Bundesliga", country: "Germania", model_validated: true },
  { slug: "ligue-1", name: "Ligue 1", country: "Francia", model_validated: true },
];

function PercentCard({ label, value }) {
  return (
    <div className="prediction-card">
      <span>{label}</span>
      <strong>{value ?? 0}%</strong>
    </div>
  );
}

function formatMetric(value, suffix = "") {
  if (value === null || value === undefined) return "n/d";
  return `${value}${suffix}`;
}

function calcolaMedieContesto(matches, tipo) {
  const filtrate = (matches || []).filter(
    (match) => match.casa_trasferta === tipo
  );

  if (!filtrate.length) return null;

  const media = (campo) => {
    const totale = filtrate.reduce(
      (somma, match) => somma + (Number(match[campo]) || 0),
      0
    );

    return Math.round((totale / filtrate.length) * 100) / 100;
  };

  return {
    partite: filtrate.length,
    possesso: media("possesso"),
    tiri_in_porta: media("tiri_in_porta"),
    tiri_fuori: media("tiri_fuori"),
    attacchi: media("attacchi"),
    attacchi_pericolosi: media("attacchi_pericolosi"),
  };
}

function MatchList({ matches, team }) {
  if (!matches?.length) return <p className="no-data">Nessun dato disponibile.</p>;

  return (
    <div className="matches-list">
      {matches.map((match, index) => (
        <div className="match-card" key={`${match.data}-${index}`}>
          <div className="match-header">
            <span>{match.data ? new Date(match.data).toLocaleDateString("it-IT") : "Data n/d"}</span>
            <span>{match.competizione || "Campionato"}</span>
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
          <div className="match-stats">
            <span>📊 {formatMetric(match.possesso, "%")} possesso</span>
            <span>🎯 {formatMetric(match.tiri_in_porta)} tiri in porta</span>
            <span>↗️ {formatMetric(match.tiri_fuori)} tiri fuori</span>
            <span>⚡ {formatMetric(match.attacchi)} attacchi</span>
            <span>🔥 {formatMetric(match.attacchi_pericolosi)} att. pericolosi</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function ContextStats({ title, stats }) {
  return (
    <div className="recent-team">
      <h4>{title}</h4>
      {!stats ? (
        <p className="no-data">Nessuna partita disponibile nel contesto richiesto.</p>
      ) : (
        <div className="stats-grid">
          <div className="stat-card"><span>📊 Possesso medio</span><strong>{formatMetric(stats.possesso, "%")}</strong></div>
          <div className="stat-card"><span>🎯 Tiri in porta</span><strong>{formatMetric(stats.tiri_in_porta)}</strong></div>
          <div className="stat-card"><span>↗️ Tiri fuori</span><strong>{formatMetric(stats.tiri_fuori)}</strong></div>
          <div className="stat-card"><span>⚡ Attacchi</span><strong>{formatMetric(stats.attacchi)}</strong></div>
          <div className="stat-card highlight"><span>🔥 Attacchi pericolosi</span><strong>{formatMetric(stats.attacchi_pericolosi)}</strong></div>
        </div>
      )}
      {stats && <p className="no-data">Media calcolata su {stats.partite} partite nel contesto.</p>}
    </div>
  );
}

function Home() {
  const [competizione, setCompetizione] = useState("serie-a");
  const [competizioni, setCompetizioni] = useState(COMPETIZIONI_FALLBACK);
  const [risultato, setRisultato] = useState(null);
  const [errore, setErrore] = useState("");
  const [caricamento, setCaricamento] = useState(false);

  useEffect(() => {
    let active = true;

    fetch("/api/competitions")
      .then((response) => response.json())
      .then((data) => {
        if (active && Array.isArray(data.competizioni) && data.competizioni.length) {
          setCompetizioni(data.competizioni);
        }
      })
      .catch(() => {
        // Manteniamo il fallback locale: la selezione resta utilizzabile.
      });

    return () => {
      active = false;
    };
  }, []);

  function cambiaCompetizione(event) {
    setCompetizione(event.target.value);
    setRisultato(null);
    setErrore("");
  }

  async function analizzaPartita(casa, ospite) {
    setErrore("");
    setRisultato(null);

    if (!casa?.trim() || !ospite?.trim()) {
      setErrore("Partita non valida.");
      return;
    }

    setCaricamento(true);

    try {
      const params = new URLSearchParams({
        casa: casa.trim(),
        ospite: ospite.trim(),
        competizione,
      });

      const response = await fetch(`/api/analyze?${params.toString()}`);
      const data = await response.json();

      if (!response.ok || data.status !== "success") {
        throw new Error(data.detail || "Impossibile completare l'analisi.");
      }

      setRisultato(data);
    } catch (error) {
      console.error(error);
      setErrore(error.message || "Impossibile completare l'analisi.");
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
  const medieCasa = calcolaMedieContesto(
    risultato?.ultime_partite?.casa,
    "casa"
  );
  const medieOspite = calcolaMedieContesto(
    risultato?.ultime_partite?.ospite,
    "trasferta"
  );

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
            Seleziona il campionato e poi una delle prossime partite in programma.
            I risultati sono stime del modello, non certezze.
          </p>

          <div className="teams-form fixture-selection-form">
            <div className="team-input competition-input">
              <label>🏆 Campionato</label>
              <select
                aria-label="Campionato"
                value={competizione}
                onChange={cambiaCompetizione}
              >
                {competizioni.map((item) => (
                  <option key={item.slug} value={item.slug}>
                    {item.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <UpcomingFixtures
            competizione={competizione}
            onAnalyze={analizzaPartita}
            analysisLoading={caricamento}
          />

          {errore && <div className="error">{errore}</div>}
        </section>

        {analisi && (
          <section className="results">
            <div className="competition-chip">
              🏆 {risultato.competizione?.name || analisi.competizione}
            </div>

            {risultato.modello?.validato === false && (
              <div className="model-warning">
                <strong>Modello sperimentale per questo campionato.</strong>
                <span>
                  I dati e l'engine xG sono attivi, ma la calibrazione probabilistica dedicata è ancora in validazione.
                </span>
              </div>
            )}

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
              <div className="section-title">
                <span>📈</span>
                <div><h3>Dati di gioco recenti</h3><p>Medie contestuali: casa in casa e ospite in trasferta</p></div>
              </div>
              <div className="recent-grid">
                <ContextStats title={`🏠 ${analisi.casa} · in casa`} stats={medieCasa} />
                <ContextStats title={`✈️ ${analisi.ospite} · in trasferta`} stats={medieOspite} />
              </div>
            </section>

            <AdvancedMetrics
              metrics={risultato.metriche_avanzate}
              home={analisi.casa}
              away={analisi.ospite}
            />

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
              <div className="section-title"><span>🔥</span><div><h3>Forma recente</h3><p>Ultime partite disponibili con statistiche avanzate</p></div></div>
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
