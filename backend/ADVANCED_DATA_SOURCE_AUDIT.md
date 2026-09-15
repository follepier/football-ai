# Football AI — audit fonti per metriche avanzate

Data audit: 2026-09-15

## Obiettivo

Verificare fonti sostenibili per aggiungere a Football AI:

- passaggi progressivi;
- line-breaking passes;
- altezza media della linea difensiva;
- recuperi nella trequarti offensiva;
- heat map di squadra.

Principio: nessuna metrica entra nel sito live o nel modello predittivo se la fonte non è sufficientemente stabile, lecita e coperta sui cinque campionati supportati.

## Esito sintetico

Al momento non è stata trovata una fonte gratuita, stabile e utilizzabile in produzione che copra in modo continuativo tutti e cinque i campionati con tutte le metriche richieste.

Le metriche restano quindi fuori dal feed live finché non troviamo una fonte compatibile. Possiamo però sviluppare e validare le formule offline usando open data con event/tracking coordinates.

## Fonti valutate

### 5DollarFootballAPI

È la fonte live già utilizzata dall'app e consente l'uso dei dati in prodotti pubblici/commerciali secondo il piano e le regole di attribuzione.

Le statistiche standard documentate comprendono attacchi, attacchi pericolosi, tiri in porta, tiri fuori e possesso, anche con split del primo tempo. Non risultano documentati passaggi progressivi, line-breaking passes, altezza della linea difensiva, recuperi nell'ultimo terzo o coordinate per heat map.

Il piano Business dichiara la possibilità di creare endpoint statistici personalizzati: è il canale più coerente da esplorare se in futuro vogliamo avere queste metriche sul feed live senza cambiare provider principale.

Decisione: mantenere come provider live principale; chiedere eventualmente disponibilità/roadmap per metriche avanzate.

### StatsBomb Open Data

Ottimo per ricerca e prototipi su event data e, dove disponibile, dati 360.

La copertura open non è però continua né corrente per tutti i cinque campionati. Esempi verificati nel file ufficiale delle competizioni:

- Bundesliga: 2023/24 disponibile con 360;
- Ligue 1: 2022/23 e 2021/22 disponibili con 360;
- La Liga: 2020/21 disponibile con 360;
- Premier League: 2015/16 e 2003/04 nell'open data;
- Serie A: 2015/16 e 1986/87 nell'open data.

Decisione: usare per R&D e validazione delle formule, non come sorgente live dei cinque campionati.

### SkillCorner Open Data

Repository ufficiale con tracking broadcast e dynamic events, ma il campione corrente open comprende 10 partite della A-League australiana 2024/25.

Decisione: utile per prototipi di altezza della linea difensiva, strutture spaziali e heat map; non adatto al feed live dei cinque campionati.

### Metrica Sports Sample Data

Offre pochi match anonimi con tracking ed eventi sincronizzati.

Decisione: utile per sviluppo metodologico e test delle formule; non adatto a copertura live.

### FotMob

Le pagine pubbliche mostrano metriche molto interessanti, tra cui line-breaking passes e possession won final 3rd. Queste ultime corrispondono bene alle metriche richieste.

Tuttavia i termini pubblicati da FotMob vietano l'uso di servizi automatici/crawler e altri metodi di utilizzo sistematico o regolare. Non useremo quindi scraping o endpoint interni non ufficiali per alimentare Football AI.

Decisione: non integrare automaticamente FotMob in produzione.

### Sports Reference / FBref

Le condizioni di utilizzo limitano l'accesso automatizzato e specificano che non si devono creare siti o strumenti basati su dati ottenuti tramite scraping senza autorizzazione. Inoltre l'accesso ad alcuni dati avanzati è stato modificato/ridotto in seguito a cambi di provider.

Decisione: non usare come feed automatizzato del sito.

### Sportmonks

Provider ufficiale e ricco di dati, con statistiche avanzate, eventi e coordinate. Il piano gratuito copre però soltanto Danish Superliga e Scottish Premiership; la copertura dei campionati desiderati richiede piani a pagamento.

Decisione: candidato commerciale da rivalutare se accettiamo un costo futuro; non soluzione gratuita attuale.

## Decisione per ciascuna metrica

| Metrica | Produzione live oggi | R&D offline | Nota |
| --- | --- | --- | --- |
| Passaggi progressivi | No | Sì | Richiedono almeno start/end coordinates dei passaggi. |
| Line-breaking passes | No | Sì | Per una definizione robusta serve contesto posizionale/360 o tracking. |
| Altezza linea difensiva | No | Sì | Richiede posizioni dei difensori o tracking affidabile. |
| Recuperi trequarti offensiva | No | Sì | FotMob li espone, ma non è una fonte automatizzabile secondo i suoi termini; serve provider autorizzato. |
| Heat map squadra | No | Sì | Realizzabile con eventi/tocchi o tracking; non va ricostruita da statistiche aggregate. |

## Piano tecnico

1. Creare un prototipo offline isolato dal motore di produzione usando StatsBomb Open Data e, quando utile, dati SkillCorner/Metrica.
2. Definire formalmente le formule di passaggio progressivo, line-breaking, altezza linea e recupero alto.
3. Prototipare la heat map di squadra con coordinate reali.
4. Validare copertura, stabilità e significato delle metriche su match open.
5. Tenere il codice R&D separato dalle API live e dal modello predittivo.
6. Attivare sul sito solo le metriche per cui troviamo una fonte live autorizzata e sostenibile sui cinque campionati.
7. Prima di usare una nuova metrica nel modello, eseguire sempre un backtest separato e confrontare l'incremento di capacità predittiva.

## Prossimo passo consigliato

Sviluppare il prototipo offline su StatsBomb Open Data, iniziando da passaggi progressivi e heat map; poi utilizzare dati 360 disponibili per sperimentare line-breaking passes e altezza della linea difensiva. Questo ci permette di costruire e testare la logica senza introdurre dati non affidabili nel sito live.
