import React from "react";
import ShotHeatmap from "./ShotHeatmap";

function MetricCard({ label, value, suffix = "" }) {
  const displayValue = value === null || value === undefined ? "n/d" : `${value}${suffix}`;

  return (
    <div className="stat-card">
      <span>{label}</span>
      <strong>{displayValue}</strong>
    </div>
  );
}

function TeamAdvancedMetrics({ title, data }) {
  if (!data) {
    return (
      <div className="recent-team">
        <h4>{title}</h4>
        <p className="no-data">Metriche avanzate non disponibili.</p>
      </div>
    );
  }

  return (
    <div className="recent-team">
      <h4>{title}</h4>
      <div className="stats-grid">
        <MetricCard label="🧱 PPDA" value={data.ppda} />
        <MetricCard label="🪄 xA medi" value={data.expected_assists_per_match} />
        <MetricCard label="🔑 Passaggi chiave medi" value={data.key_passes_per_match} />
        <MetricCard label="📍 Field Tilt proxy" value={data.field_tilt_proxy} suffix="%" />
        <MetricCard label="➡️ Deep completions" value={data.deep_completions_per_match} />
        <MetricCard label="⬅️ Deep allowed" value={data.deep_allowed_per_match} />
        <MetricCard label="🧤 Salvataggi in area" value={data.saves_inside_box_per_match} />
      </div>
      <p className="no-data">
        PPDA, xA, passaggi chiave, deep completions, deep allowed e Field Tilt: stagione corrente · {data.matches ?? 0} partite · fonte {data.source || "Understat"}.
      </p>
      <p className="no-data">
        Salvataggi in area: media sulle ultime {data.saves_inside_box_matches ?? 0} partite disponibili.
      </p>

      <ShotHeatmap data={data.shot_heatmap} extras={data.shot_extras} />
    </div>
  );
}

export default function AdvancedMetrics({ metrics, home, away }) {
  if (!metrics) return null;

  return (
    <section className="section">
      <div className="section-title">
        <span>🧠</span>
        <div>
          <h3>Metriche avanzate</h3>
          <p>Pressing, creazione, profondità, territorio e mappa dei tiri su dati Understat</p>
        </div>
      </div>

      <div className="recent-team">
        <p className="no-data">
          <strong>PPDA</strong> · Passes Per Defensive Action: indica quanti passaggi vengono concessi all'avversario prima di un'azione difensiva. In generale, un valore più basso segnala un pressing più intenso; un valore più alto un pressing meno aggressivo.
        </p>
        <p className="no-data">
          <strong>Field Tilt proxy</strong> · misura quanto una squadra riesce a portare il gioco in profondità rispetto all'avversario. Un valore sopra il 50% indica una maggiore presenza territoriale offensiva. Qui è stimato con la quota di deep completions sul totale deep + deep allowed, quindi non è il Field Tilt event-based puro.
        </p>
        <p className="no-data">
          <strong>Deep completions</strong> · azioni completate in una zona molto profonda vicino alla porta avversaria. <strong>Deep allowed</strong> indica quante ne vengono concesse agli avversari: meno è meglio dal punto di vista difensivo.
        </p>
        <p className="no-data">
          <strong>Salvataggi in area</strong> · media dei tiri avversari partiti dall'interno dell'area e respinti dal portiere nelle ultime partite disponibili. È una metrica descrittiva e non modifica ancora il motore predittivo.
        </p>
        <p className="no-data">
          <strong>Mappa dei tiri</strong> · usa le coordinate reali dei tiri Understat delle ultime partite. L'intensità evidenzia le zone che hanno prodotto più xG complessivo; non va confusa con una heat map completa di tutti i tocchi della squadra.
        </p>
        <p className="no-data">
          <strong>Qualità offensiva recente</strong> · npxG, Gol − xG, quota di xG da palla inattiva e distanza media di tiro descrivono come viene prodotta la pericolosità nelle ultime partite. Restano indicatori descrittivi e non entrano ancora nel modello predittivo.
        </p>
      </div>

      {metrics.status !== "success" ? (
        <p className="no-data">
          Metriche avanzate temporaneamente non disponibili. L'analisi principale resta valida.
        </p>
      ) : (
        <div className="recent-grid">
          <TeamAdvancedMetrics title={`🏠 ${home}`} data={metrics.home} />
          <TeamAdvancedMetrics title={`✈️ ${away}`} data={metrics.away} />
        </div>
      )}
    </section>
  );
}
