import React from "react";
import "./ShotHeatmap.css";

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
          const opacity = Math.max(0.04, Math.min(0.88, 0.06 + (cell.intensity || 0) * 0.82));
          return (
            <rect
              key={`${cell.row}-${cell.column}`}
              className="shot-heat-cell"
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
        Intensità delle celle basata sull'xG cumulato dei tiri. È una mappa dei tiri, non una heat map completa dei tocchi della squadra.
      </p>
    </div>
  );
}

export default ShotHeatmap;
