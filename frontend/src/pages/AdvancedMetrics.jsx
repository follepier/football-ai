import React from "react";

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
      </div>
      <p className="no-data">
        Media stagione corrente · {data.matches ?? 0} partite · fonte {data.source || "Understat"}.
      </p>
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
          <p>PPDA, expected assist e passaggi chiave su dati Understat</p>
        </div>
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

      <p className="no-data">
        Field Tilt e salvataggi su tiri in area sono in audit separato prima della pubblicazione.
      </p>
    </section>
  );
}
