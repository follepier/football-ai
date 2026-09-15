import React from "react";
import "./ShotHeatmap.css";

const SITUATION_LABELS = {
  OpenPlay: "Azione",
  FromCorner: "Da corner",
  SetPiece: "Palla inattiva",
  DirectFreekick: "Punizione diretta",
  Penalty: "Rigore",
  Unknown: "Altro",
};

function formatNumber(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "n/d";
  }
  return Number(value).toFixed(digits).replace(/\.0$/, "");
}

function DistributionRow({ label, shots, share, xg }) {
  const width = Math.max(0, Math.min(100, Number(share) || 0));

  return (
    <div className="shot-distribution-row">
      <div className="shot-distribution-label">
        <span>{label}</span>
        <span>{shots ?? 0} tiri · {formatNumber(share)}% · xG {formatNumber(xg, 2)}</span>
      </div>
      <div className="shot-distribution-track" aria-hidden="true">
        <span style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

function ShotProfile({ data }) {
  const profile = data?.profile;
  if (!profile) return null;

  const lanes = profile.lateral_distribution || {};
  const situations = Array.isArray(profile.situations) ? profile.situations : [];

  return (
    <div className="shot-profile">
      <div className="shot-profile-summary">
        <div className="shot-profile-card">
          <span>Tiri in area</span>
          <strong>{formatNumber(profile.shots_inside_box_share_pct)}%</strong>
          <small>{profile.shots_inside_box ?? 0} su {data.shots ?? 0} tiri</small>
        </div>
        <div className="shot-profile-card">
          <span>xG medio per tiro</span>
          <strong>{formatNumber(data.xg_per_shot, 3)}</strong>
          <small>qualità media delle conclusioni</small>
        </div>
        <div className="shot-profile-card">
          <span>Tiri per partita</span>
          <strong>{formatNumber(data.shots_per_match, 2)}</strong>
          <small>ultime {data.matches ?? 0} partite</small>
        </div>
      </div>

      <div className="shot-profile-block">
        <h6>Distribuzione laterale dei tiri</h6>
        <DistributionRow
          label="Sinistra"
          shots={lanes.left?.shots}
          share={lanes.left?.share_pct}
          xg={lanes.left?.xg}
        />
        <DistributionRow
          label="Centro"
          shots={lanes.center?.shots}
          share={lanes.center?.share_pct}
          xg={lanes.center?.xg}
        />
        <DistributionRow
          label="Destra"
          shots={lanes.right?.shots}
          share={lanes.right?.share_pct}
          xg={lanes.right?.xg}
        />
        <p className="no-data shot-profile-note">
          Sinistra, centro e destra sono riferiti alla direzione d'attacco e alla coordinata trasversale Understat.
        </p>
      </div>

      {situations.length > 0 && (
        <div className="shot-profile-block">
          <h6>Origine delle conclusioni</h6>
          {situations.map((item) => (
            <DistributionRow
              key={item.situation}
              label={SITUATION_LABELS[item.situation] || item.situation}
              shots={item.shots}
              share={item.share_pct}
              xg={item.xg}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ShotHeatmap({ data }) {
  if (!data || !data.shots || !Array.isArray(data.cells)) {
    return (
      <div className="shot-heatmap-wrap">
        <h5>🔥 Mappa dei tiri recenti</h5>
        <p className="no-data">Nessun tiro con coordinate disponibile.</p>
      </div>
    );
  }

  const columns = data.columns || 8;
  const rows = data.rows || 6;
  const cellWidth = 100 / columns;
  const cellHeight = 64 / rows;

  return (
    <div className="shot-heatmap-wrap">
      <div className="shot-heatmap-heading">
        <h5>🔥 Mappa dei tiri recenti</h5>
        <span>
          {data.shots} tiri · xG {data.xg_total ?? "n/d"} · {data.matches ?? 0} partite
        </span>
      </div>

      <svg
        className="shot-heatmap"
        viewBox="0 0 100 64"
        role="img"
        aria-label="Mappa dei tiri recenti della squadra"
      >
        <rect className="shot-pitch-bg" x="0" y="0" width="100" height="64" rx="1.5" />

        {data.cells.map((cell) => {
          const hasShots = (cell.shots || 0) > 0;
          const rawIntensity = Math.max(0, Math.min(1, cell.intensity || 0));
          const visualIntensity = Math.sqrt(rawIntensity);
          const opacity = hasShots
            ? Math.max(0.2, Math.min(0.9, 0.2 + visualIntensity * 0.7))
            : 0;

          return (
            <rect
              key={`${cell.row}-${cell.column}`}
              className={hasShots ? "shot-heat-cell shot-heat-cell-active" : "shot-heat-cell"}
              x={cell.column * cellWidth}
              y={cell.row * cellHeight}
              width={cellWidth}
              height={cellHeight}
              style={{ opacity }}
            >
              <title>
                {`${cell.shots} tiri · xG ${cell.xg}`}
              </title>
            </rect>
          );
        })}

        <g className="shot-pitch-lines">
          <rect x="0.8" y="0.8" width="98.4" height="62.4" rx="1" />
          <line x1="50" y1="0.8" x2="50" y2="63.2" />
          <circle cx="50" cy="32" r="8.7" />
          <circle cx="50" cy="32" r="0.7" />
          <rect x="83.3" y="13.5" width="15.9" height="37" />
          <rect x="93" y="23.5" width="6.2" height="17" />
          <circle cx="89" cy="32" r="0.65" />
          <path d="M 83.3 24 A 8.7 8.7 0 0 0 83.3 40" />
          <line x1="99.2" y1="27.5" x2="99.2" y2="36.5" />
        </g>
      </svg>

      <div className="shot-heatmap-legend">
        <span>← costruzione</span>
        <span>porta avversaria →</span>
      </div>
      <p className="no-data shot-heatmap-note">
        Intensità basata sull'xG cumulato, con scala visiva non lineare per rendere leggibili anche le zone con pochi tiri o basso xG. Le celle senza tiri restano vuote. È una mappa dei tiri, non una heat map completa dei tocchi della squadra.
      </p>

      <ShotProfile data={data} />
    </div>
  );
}

export default ShotHeatmap;
