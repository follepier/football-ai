import React, { useEffect, useState } from "react";

function formatKickoff(value) {
  if (!value) return "Orario da definire";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Orario da definire";

  return date.toLocaleString("it-IT", {
    weekday: "short",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function UpcomingFixtures({
  competizione,
  onAnalyze,
  analysisLoading = false,
}) {
  const [partite, setPartite] = useState([]);
  const [caricamento, setCaricamento] = useState(true);
  const [errore, setErrore] = useState("");
  const [selezionata, setSelezionata] = useState(null);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();

    setPartite([]);
    setErrore("");
    setCaricamento(true);
    setSelezionata(null);

    fetch(
      `/api/competitions/${encodeURIComponent(competizione)}/fixtures/upcoming?limit=20`,
      { signal: controller.signal }
    )
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok || data.status !== "success") {
          throw new Error(data.detail || "Impossibile caricare le prossime partite.");
        }
        return data;
      })
      .then((data) => {
        if (active) {
          setPartite(Array.isArray(data.partite) ? data.partite : []);
        }
      })
      .catch((error) => {
        if (active && error.name !== "AbortError") {
          setErrore(error.message || "Impossibile caricare le prossime partite.");
        }
      })
      .finally(() => {
        if (active) setCaricamento(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [competizione]);

  async function scegliPartita(partita) {
    if (analysisLoading) return;

    const key = partita.id ?? `${partita.kickoff_ts}-${partita.home}-${partita.away}`;
    setSelezionata(key);

    try {
      await onAnalyze(partita.home, partita.away, partita);
    } finally {
      setSelezionata(null);
    }
  }

  if (caricamento) {
    return <div className="fixtures-state">Caricamento prossime partite...</div>;
  }

  if (errore) {
    return <div className="error fixtures-error">{errore}</div>;
  }

  if (!partite.length) {
    return (
      <div className="fixtures-state">
        Nessuna partita futura disponibile al momento per questo campionato.
      </div>
    );
  }

  return (
    <div className="upcoming-fixtures">
      <div className="fixtures-heading">
        <div>
          <h3>Prossime partite</h3>
          <p>Seleziona una partita per avviare subito l'analisi.</p>
        </div>
        <span>{partite.length} disponibili</span>
      </div>

      <div className="fixtures-grid">
        {partite.map((partita) => {
          const key = partita.id ?? `${partita.kickoff_ts}-${partita.home}-${partita.away}`;
          const isLoading = analysisLoading && selezionata === key;

          return (
            <button
              type="button"
              className="fixture-card"
              key={key}
              onClick={() => scegliPartita(partita)}
              disabled={analysisLoading}
            >
              <span className="fixture-date">{formatKickoff(partita.kickoff_utc)}</span>
              <div className="fixture-teams">
                <strong>{partita.home}</strong>
                <span>VS</span>
                <strong>{partita.away}</strong>
              </div>
              <span className="fixture-action">
                {isLoading ? "Analisi in corso..." : "Analizza partita →"}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
