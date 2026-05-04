import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const FIXED_URL = "https://betting.co.zw/sportsbook/upcoming";
const LATEST_RESULT_KEY = "latest_scan_result";
let inMemoryScanResult = null;

function navigate(path) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function usePath() {
  const [path, setPath] = useState(window.location.pathname + window.location.search);
  useEffect(() => {
    const onPop = () => setPath(window.location.pathname + window.location.search);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  return path;
}

function App() {
  const path = usePath();
  const route = path.split("?")[0];

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Read-only extractor</p>
          <h1>Website Content Reader</h1>
        </div>
        <nav className="tabs" aria-label="Pages">
          <button className={route === "/reader" ? "active" : ""} onClick={() => navigate("/reader")}>Reader</button>
          <button className={route === "/results" ? "active" : ""} onClick={() => navigate("/results")}>Results</button>
          <button className={route === "/arbitrage" ? "active" : ""} onClick={() => navigate("/arbitrage")}>Arbitrage</button>
          <button className={route === "/logs" ? "active" : ""} onClick={() => navigate("/logs")}>Logs</button>
        </nav>
      </header>

      <main>
        {route === "/logs" ? <LogsPage /> : route === "/arbitrage" ? <ArbitragePage /> : route === "/results" ? <ResultsPage /> : <ReaderPage />}
      </main>
    </div>
  );
}

function ReaderPage() {
  const [isReading, setIsReading] = useState(false);
  const [progress, setProgress] = useState([]);
  const [error, setError] = useState("");
  const [totalStake, setTotalStake] = useState(100);

  async function startScan() {
    setIsReading(true);
    setError("");
    setProgress(["Opening fixed URL", "Trying normal HTML extraction"]);

    const progressTimers = [
      setTimeout(() => setProgress((items) => [...items, "Waiting for dynamic content"]), 900),
      setTimeout(() => setProgress((items) => [...items, "Using browser automation if needed"]), 1800),
      setTimeout(() => setProgress((items) => [...items, "Capturing screenshots if fallback is needed"]), 2700),
      setTimeout(() => setProgress((items) => [...items, "Cleaning text and formatting JSON"]), 3600),
      setTimeout(() => setProgress((items) => [...items, "Calculating arbitrage by complete market"]), 4500)
    ];

    try {
      const response = await fetch("/api/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: FIXED_URL, total_stake: Number(totalStake) || 100 })
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Scan failed");
      }
      rememberScanResult(payload);
      setProgress((items) => [...items, "Scan complete"]);
      navigate(`/arbitrage?session=${encodeURIComponent(payload.id)}`);
    } catch (err) {
      setError(err.message || "Scan failed");
    } finally {
      progressTimers.forEach(clearTimeout);
      setIsReading(false);
    }
  }

  return (
    <section className="reader-grid">
      <div className="tool-panel">
        <div className="field-row">
          <label htmlFor="fixed-url">Fixed URL</label>
          <input id="fixed-url" value={FIXED_URL} readOnly />
        </div>
        <div className="field-row stake-row">
          <label htmlFor="total-stake">Total Stake</label>
          <input
            id="total-stake"
            type="number"
            min="1"
            step="0.01"
            value={totalStake}
            onChange={(event) => setTotalStake(event.target.value)}
          />
        </div>
        <button className="primary-action" type="button" onClick={startScan} disabled={isReading}>
          {isReading ? "Reading..." : "Read Website"}
        </button>
        {error && <p className="error-text">{error}</p>}
      </div>

      <div className="progress-panel">
        <h2>Scan Progress</h2>
        <ol className="progress-list">
          {progress.length === 0 ? <li>Ready</li> : progress.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
        </ol>
        {isReading && <div className="loading-bar"><span /></div>}
      </div>
    </section>
  );
}

function ResultsPage() {
  const { result, error } = useSessionResult();

  const events = useMemo(() => flattenEvents(result?.structured_content), [result]);
  const odds = useMemo(() => flattenOdds(result?.structured_content), [result]);
  const sports = result?.section_1_all_available_sporting_events_and_odds?.sports || result?.structured_content?.sports || [];
  const arbitrageAnalysis = result?.section_2_arbitrage_analysis || {};
  const arbitrageSummary = result?.section_3_arbitrage_summary || {};

  if (error) {
    return <EmptyState message={error} action="Run a scan" onAction={() => navigate("/reader")} />;
  }
  if (!result) {
    return <EmptyState message="Loading results" />;
  }

  return (
    <div className="results-layout">
      <section className="metrics-strip">
        <Metric label="Status" value={result.scan_status} />
        <Metric label="Method" value={formatMethod(result.extraction_method)} />
        <Metric label="Confidence" value={`${result.confidence_score}%`} />
        <Metric label="Total Stake" value={formatMoney(result.total_stake || 100)} />
        <Metric label="Events" value={events.length} />
        <Metric label="Odds" value={odds.length} />
        <Metric label="Markets Analyzed" value={arbitrageSummary.complete_markets_analyzed || 0} />
        <Metric label="Arbitrage Found" value={arbitrageSummary.arbitrage_opportunities_found || 0} />
      </section>

      <section className="summary-panel">
        <div>
          <p className="eyebrow">Source</p>
          <h2>{result.page_title || "Untitled page"}</h2>
          <a href={result.source_url} target="_blank" rel="noreferrer">{result.source_url}</a>
        </div>
        <pre className="summary-text">{result.summary?.summary_text}</pre>
      </section>

      <section className="split-grid">
        <div className="data-panel">
          <h2>Raw Extracted Text</h2>
          <div className="raw-text">
            {(result.raw_text || []).map((line, index) => <p key={`${line}-${index}`}>{line}</p>)}
          </div>
        </div>

        <div className="data-panel">
          <h2>Structured JSON</h2>
          <pre className="json-view compact-json">{JSON.stringify(result, null, 2)}</pre>
        </div>
      </section>

      <AvailableOddsSection sports={sports} />

      <ArbitrageAnalysisSection analysis={arbitrageAnalysis} />

      <ArbitrageSummarySection summary={arbitrageSummary} timestamp={result.timestamp} />

      {result.warnings?.length > 0 && (
        <section className="warning-band">
          {result.warnings.map((warning, index) => <span key={`${warning}-${index}`}>{warning}</span>)}
        </section>
      )}
    </div>
  );
}

function ArbitragePage() {
  const { result, error } = useSessionResult();

  if (error) {
    return <EmptyState message={error} action="Run a scan" onAction={() => navigate("/reader")} />;
  }
  if (!result) {
    return <EmptyState message="Loading arbitrage calculations" />;
  }

  const analysis = result.section_2_arbitrage_analysis || {};
  const summary = result.section_3_arbitrage_summary || {};
  const eventAnalyses = analysis.event_analyses || buildEventAnalysesFallback(result);
  const opportunities = analysis.arbitrage_opportunities || [];

  return (
    <div className="results-layout">
      <section className="metrics-strip">
        <Metric label="Events" value={eventAnalyses.length} />
        <Metric label="Markets Analyzed" value={summary.complete_markets_analyzed || 0} />
        <Metric label="Markets Skipped" value={summary.incomplete_markets_skipped || 0} />
        <Metric label="Arbitrage Events" value={eventAnalyses.filter((event) => event.has_arbitrage_opportunity).length} />
        <Metric label="Opportunities" value={summary.arbitrage_opportunities_found || 0} />
        <Metric label="Best Profit" value={formatPercent(summary.best_arbitrage_profit_percentage || 0)} />
        <Metric label="Stake" value={formatMoney(result.total_stake || 100)} />
        <Metric label="Scan Confidence" value={`${result.confidence_score || 0}%`} />
      </section>

      <section className="summary-panel">
        <div>
          <p className="eyebrow">Arbitrage Calculations</p>
          <h2>Every Event And Market</h2>
          <a href={result.source_url} target="_blank" rel="noreferrer">{result.source_url}</a>
        </div>
        <pre className="summary-text">
{`Each event below shows whether any complete market has arbitrage.
Complete markets include full calculation proof.
Incomplete markets are flagged and not treated as arbitrage.`}
        </pre>
      </section>

      <section className="data-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Positive Only</p>
            <h2>Arbitrage Opportunities</h2>
          </div>
          <span>{opportunities.length} found</span>
        </div>
        <div className="opportunity-band">
          {opportunities.length ? opportunities.map((market, index) => (
            <OpportunityCard key={`${market.event}-${market.market}-${index}`} market={market} rank={index + 1} />
          )) : <p className="muted-text">No positive arbitrage opportunities were found in the latest scan.</p>}
        </div>
      </section>

      <section className="data-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Every Event</p>
            <h2>Arbitrage Calculation By Event</h2>
          </div>
          <span>{eventAnalyses.length} events</span>
        </div>
        <div className="event-analysis-stack">
          {eventAnalyses.length ? eventAnalyses.map((eventAnalysis, index) => (
            <EventArbitrageCard key={`${eventAnalysis.event_key || eventAnalysis.event}-${index}`} eventAnalysis={eventAnalysis} />
          )) : <p className="muted-text">No events were available for arbitrage calculation.</p>}
        </div>
      </section>

      <ArbitrageSummarySection summary={summary} timestamp={result.timestamp} />

      {result.warnings?.length > 0 && (
        <section className="warning-band">
          {result.warnings.map((warning, index) => <span key={`${warning}-${index}`}>{warning}</span>)}
        </section>
      )}
    </div>
  );
}

function EventArbitrageCard({ eventAnalysis }) {
  const hasArb = Boolean(eventAnalysis.has_arbitrage_opportunity);
  return (
    <article className={`event-arbitrage-card ${hasArb ? "positive" : "negative"}`}>
      <div className="event-arbitrage-header">
        <div>
          <strong>{eventAnalysis.event}</strong>
          <span>{eventAnalysis.sport} / {eventAnalysis.competition}</span>
          <span>Start time: {[eventAnalysis.start_date, eventAnalysis.start_time].filter(Boolean).join(", ") || "Not found"}</span>
        </div>
        <span className={`status-pill ${hasArb ? "yes" : "no"}`}>
          Event arbitrage: {hasArb ? "Yes" : "No"}
        </span>
      </div>

      <div className="event-result-row">
        <Metric label="Markets Found" value={eventAnalysis.markets_found || 0} />
        <Metric label="Odds Extracted" value={eventAnalysis.odds_extracted || 0} />
        <Metric label="Analyzed" value={eventAnalysis.complete_markets_analyzed || 0} />
        <Metric label="Skipped" value={eventAnalysis.incomplete_markets_skipped || 0} />
        <Metric label="Best Profit" value={formatPercent(eventAnalysis.best_profit_percentage || 0)} />
      </div>

      <p className="event-result-text">{eventAnalysis.event_result}</p>

      {(eventAnalysis.analyzed_markets || []).length > 0 && (
        <div className="event-market-calculations">
          <h3>Calculated Markets</h3>
          {(eventAnalysis.analyzed_markets || []).map((market, index) => (
            <AnalysisCard key={`${market.market}-${index}`} market={market} />
          ))}
        </div>
      )}

      {(eventAnalysis.skipped_markets || []).length > 0 && (
        <div className="skipped-markets event-skipped-markets">
          <h3>Incomplete Markets For This Event</h3>
          <DataTable
            columns={["Market", "Outcomes", "Odds Found", "Reason"]}
            rows={(eventAnalysis.skipped_markets || []).map((market) => [
              market.market,
              market.number_of_outcomes_found,
              (market.odds_found || []).map((odd) => `${odd.selection_name}: ${odd.odds}`).join(", "),
              market.skip_reason
            ])}
          />
        </div>
      )}
    </article>
  );
}

function AvailableOddsSection({ sports }) {
  return (
    <section className="data-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Section 1</p>
          <h2>All Available Sporting Events And Odds</h2>
        </div>
        <span>{sports.length} sports</span>
      </div>
      <div className="event-stack">
        {sports.length ? sports.map((sport) => (
          <SportBlock key={sport.sport_name} sport={sport} />
        )) : <p className="muted-text">No sporting events were extracted.</p>}
      </div>
    </section>
  );
}

function SportBlock({ sport }) {
  return (
    <article className="sport-block">
      <div className="sport-heading">
        <strong>{sport.sport_name}</strong>
        <span>{countEvents(sport)} events</span>
      </div>
      {(sport.competitions || []).map((competition, competitionIndex) => (
        <div className="competition-block" key={`${sport.sport_name}-${competition.competition_name}-${competitionIndex}`}>
          <h3>{competition.competition_name || "Unspecified competition"}</h3>
          {(competition.events || []).map((event, eventIndex) => (
            <EventOddsCard
              key={`${event.event_name}-${event.start_time}-${eventIndex}`}
              event={event}
            />
          ))}
        </div>
      ))}
    </article>
  );
}

function EventOddsCard({ event }) {
  return (
    <div className="event-card">
      <div className="event-card-header">
        <div>
          <strong>{event.event_name}</strong>
          <span>Start time: {[event.start_date, event.start_time].filter(Boolean).join(", ") || "Not found"}</span>
        </div>
      </div>
      {(event.markets || []).map((market, marketIndex) => (
        <div className="market-block" key={`${market.market_name}-${marketIndex}`}>
          <div className="market-title">
            <span>Market: {market.market_name || "Unspecified market"}</span>
            <span>Status: {market.market_status || "Not found"}</span>
            <span>Confidence: {market.confidence_score ?? "Not found"}</span>
          </div>
          <DataTable
            columns={["Selection", "Odds", "Confidence"]}
            rows={(market.selections || []).map((selection) => [
              selection.selection_name,
              selection.odds,
              selection.confidence_score ?? market.confidence_score ?? ""
            ])}
          />
        </div>
      ))}
    </div>
  );
}

function ArbitrageAnalysisSection({ analysis }) {
  const analyzed = analysis.analyzed_markets || [];
  const opportunities = analysis.arbitrage_opportunities || [];
  const skipped = analysis.skipped_markets || [];

  return (
    <section className="data-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Section 2</p>
          <h2>Arbitrage Analysis</h2>
        </div>
        <span>{analyzed.length} complete markets</span>
      </div>

      <div className="opportunity-band">
        <h3>Arbitrage Opportunities</h3>
        {opportunities.length ? opportunities.map((market, index) => (
          <OpportunityCard key={`${market.event}-${market.market}-${index}`} market={market} rank={index + 1} />
        )) : <p className="muted-text">No positive arbitrage opportunities were found.</p>}
      </div>

      <div className="analysis-list">
        <h3>Every Complete Market Analyzed</h3>
        {analyzed.length ? analyzed.map((market, index) => (
          <AnalysisCard key={`${market.event}-${market.market}-${index}`} market={market} />
        )) : <p className="muted-text">No complete markets were available for analysis.</p>}
      </div>

      {skipped.length > 0 && (
        <div className="skipped-markets">
          <h3>Incomplete Markets Skipped</h3>
          <DataTable
            columns={["Sport", "Event", "Market", "Outcomes", "Reason"]}
            rows={skipped.map((market) => [
              market.sport,
              market.event,
              market.market,
              market.number_of_outcomes_found,
              market.skip_reason
            ])}
          />
        </div>
      )}
    </section>
  );
}

function OpportunityCard({ market, rank }) {
  return (
    <article className="opportunity-card">
      <div>
        <span className="rank-pill">#{rank}</span>
        <strong>{market.event}</strong>
        <span>{market.sport} / {market.competition} / {market.market}</span>
      </div>
      <div className="opportunity-metrics">
        <Metric label="Profit" value={formatPercent(market.profit_percentage)} />
        <Metric label="Guaranteed Profit" value={formatMoney(market.guaranteed_profit)} />
        <Metric label="Guaranteed Payout" value={formatMoney(market.guaranteed_payout)} />
      </div>
    </article>
  );
}

function AnalysisCard({ market }) {
  return (
    <article className={`analysis-card ${market.arbitrage_exists ? "positive" : "negative"}`}>
      <div className="analysis-card-header">
        <div>
          <strong>{market.event}</strong>
          <span>{market.sport} / {market.competition} / {market.market}</span>
        </div>
        <span className={`status-pill ${market.arbitrage_exists ? "yes" : "no"}`}>
          Arbitrage: {market.arbitrage_exists ? "Yes" : "No"}
        </span>
      </div>

      <DataTable
        columns={["Selection", "Odds", "Implied Probability"]}
        rows={(market.implied_probabilities || []).map((selection) => [
          selection.selection_name,
          selection.odds,
          formatProbability(selection.implied_probability)
        ])}
      />

      <div className="calculation-grid">
        <Metric label="Outcomes" value={market.number_of_outcomes} />
        <Metric label="Total Implied" value={formatProbability(market.total_implied_probability)} />
        <Metric
          label={market.arbitrage_exists ? "Arb Margin" : "Bookmaker Margin"}
          value={formatProbability(market.arbitrage_exists ? market.arbitrage_margin : market.bookmaker_margin)}
        />
        <Metric
          label={market.arbitrage_exists ? "Profit" : "Margin %"}
          value={formatPercent(market.arbitrage_exists ? market.profit_percentage : market.bookmaker_margin_percentage)}
        />
      </div>

      {market.arbitrage_exists && (
        <DataTable
          columns={["Selection", "Stake", "Payout"]}
          rows={(market.recommended_stake_allocation || []).map((selection) => [
            selection.selection_name,
            formatMoney(selection.stake),
            formatMoney(selection.payout)
          ])}
        />
      )}

      <div className="proof-box">
        {(market.calculation_proof || []).map((line, index) => <p key={`${line}-${index}`}>{line}</p>)}
        <p>{market.result_explanation}</p>
      </div>
    </article>
  );
}

function ArbitrageSummarySection({ summary, timestamp }) {
  return (
    <section className="data-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Section 3</p>
          <h2>Arbitrage Summary</h2>
        </div>
        <span>{timestamp}</span>
      </div>
      <div className="summary-metrics-grid">
        <Metric label="Sports Found" value={summary.sports_found || 0} />
        <Metric label="Competitions" value={summary.competitions_found || 0} />
        <Metric label="Events" value={summary.events_found || 0} />
        <Metric label="Markets" value={summary.markets_found || 0} />
        <Metric label="Odds Extracted" value={summary.odds_extracted || 0} />
        <Metric label="Complete Markets" value={summary.complete_markets_analyzed || 0} />
        <Metric label="Incomplete Skipped" value={summary.incomplete_markets_skipped || 0} />
        <Metric label="Opportunities" value={summary.arbitrage_opportunities_found || 0} />
        <Metric label="Best Profit" value={formatPercent(summary.best_arbitrage_profit_percentage || 0)} />
      </div>
      {summary.best_arbitrage_opportunity && (
        <div className="best-summary">
          <strong>Best arbitrage opportunity</strong>
          <span>
            {summary.best_arbitrage_opportunity.event} / {summary.best_arbitrage_opportunity.market}
            {" "}at {formatPercent(summary.best_arbitrage_opportunity.profit_percentage)}
          </span>
        </div>
      )}
    </section>
  );
}

function LogsPage() {
  const [sessions, setSessions] = useState([]);
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    fetch("/api/sessions").then((response) => response.json()).then(setSessions).catch(() => setSessions([]));
    fetch("/api/logs").then((response) => response.json()).then(setLogs).catch(() => setLogs([]));
  }, []);

  return (
    <div className="logs-layout">
      <section className="data-panel">
        <h2>Reading Sessions</h2>
        <DataTable
          columns={["Started", "Status", "Method", "Confidence", "Title"]}
          rows={sessions.map((session) => [
            session.started_at,
            session.scan_status,
            formatMethod(session.extraction_method),
            `${session.confidence_score || 0}%`,
            session.page_title || ""
          ])}
        />
      </section>

      <section className="data-panel">
        <h2>Extraction Logs</h2>
        <DataTable
          columns={["Time", "Level", "Message"]}
          rows={logs.map((log) => [log.created_at, log.level, log.message])}
        />
      </section>
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function DataTable({ columns, rows }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr>
        </thead>
        <tbody>
          {rows.length ? rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => <td key={`${rowIndex}-${cellIndex}`}>{cell || " "}</td>)}
            </tr>
          )) : (
            <tr><td colSpan={columns.length}>No rows found</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function EmptyState({ message, action, onAction }) {
  return (
    <section className="empty-state">
      <h2>{message}</h2>
      {action && <button className="primary-action" type="button" onClick={onAction}>{action}</button>}
    </section>
  );
}

function useSessionResult() {
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const sessionId = new URLSearchParams(window.location.search).get("session") || readLatestSessionId();

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setError("");
      const cached = readStoredScanResult(sessionId);
      if (cached && !cancelled) {
        setResult(cached);
      }

      const url = sessionId ? `/api/sessions/${encodeURIComponent(sessionId)}` : "/api/sessions/latest";
      try {
        const response = await fetch(url);
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.detail || "No results found");
        }
        rememberScanResult(payload);
        if (!cancelled) setResult(payload);
      } catch (err) {
        if (!cancelled && !cached) setError(err.message || "No results found");
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  return { result, error };
}

function rememberScanResult(result) {
  if (!result) return;
  inMemoryScanResult = result;
  try {
    if (result.id) {
      localStorage.setItem("latest_session_id", result.id);
    }
    localStorage.setItem(LATEST_RESULT_KEY, JSON.stringify(result));
  } catch {
    try {
      sessionStorage.setItem(LATEST_RESULT_KEY, JSON.stringify(result));
    } catch {
      // The in-memory copy still covers immediate navigation after a scan.
    }
  }
}

function readStoredScanResult(sessionId) {
  if (matchesStoredSession(inMemoryScanResult, sessionId)) {
    return inMemoryScanResult;
  }

  for (const store of [localStorage, sessionStorage]) {
    try {
      const raw = store.getItem(LATEST_RESULT_KEY);
      if (!raw) continue;
      const parsed = JSON.parse(raw);
      if (matchesStoredSession(parsed, sessionId)) {
        inMemoryScanResult = parsed;
        return parsed;
      }
    } catch {
      // Ignore unreadable browser storage and fall back to the API.
    }
  }
  return null;
}

function matchesStoredSession(result, sessionId) {
  if (!result) return false;
  if (!sessionId) return true;
  return result.id === sessionId;
}

function readLatestSessionId() {
  try {
    return localStorage.getItem("latest_session_id");
  } catch {
    return inMemoryScanResult?.id || null;
  }
}

function flattenEvents(structured) {
  const rows = [];
  for (const sport of structured?.sports || []) {
    for (const competition of sport.competitions || []) {
      for (const event of competition.events || []) {
        rows.push({
          sport_name: sport.sport_name,
          competition_name: competition.competition_name,
          event_name: event.event_name,
          start_date: event.start_date,
          start_time: event.start_time
        });
      }
    }
  }
  return rows;
}

function buildEventAnalysesFallback(result) {
  const analyzed = result?.section_2_arbitrage_analysis?.analyzed_markets || [];
  const skipped = result?.section_2_arbitrage_analysis?.skipped_markets || [];
  const events = flattenEvents(result?.structured_content);

  return events.map((event) => {
    const eventAnalyzed = analyzed.filter((market) => (
      market.sport === event.sport_name &&
      market.competition === event.competition_name &&
      market.event === event.event_name &&
      (market.start_date || "") === (event.start_date || "") &&
      (market.start_time || "") === (event.start_time || "")
    ));
    const eventSkipped = skipped.filter((market) => (
      market.sport === event.sport_name &&
      market.competition === event.competition_name &&
      market.event === event.event_name &&
      (market.start_date || "") === (event.start_date || "") &&
      (market.start_time || "") === (event.start_time || "")
    ));
    const hasArb = eventAnalyzed.some((market) => market.arbitrage_exists);
    return {
      sport: event.sport_name,
      competition: event.competition_name,
      event: event.event_name,
      start_date: event.start_date,
      start_time: event.start_time,
      markets_found: eventAnalyzed.length + eventSkipped.length,
      odds_extracted: [...eventAnalyzed, ...eventSkipped].reduce((total, market) => (
        total + (market.odds_used?.length || market.odds_found?.length || 0)
      ), 0),
      complete_markets_analyzed: eventAnalyzed.length,
      incomplete_markets_skipped: eventSkipped.length,
      has_arbitrage_opportunity: hasArb,
      best_profit_percentage: Math.max(0, ...eventAnalyzed.map((market) => market.profit_percentage || 0)),
      event_result: hasArb ? "Arbitrage opportunity found in this event." : "No arbitrage opportunity found in any complete market for this event.",
      analyzed_markets: eventAnalyzed,
      skipped_markets: eventSkipped
    };
  });
}

function flattenOdds(structured) {
  const rows = [];
  for (const sport of structured?.sports || []) {
    for (const competition of sport.competitions || []) {
      for (const event of competition.events || []) {
        for (const market of event.markets || []) {
          for (const selection of market.selections || []) {
            rows.push({
              sport_name: sport.sport_name,
              competition_name: competition.competition_name,
              event_name: event.event_name,
              market_name: market.market_name,
              selection_name: selection.selection_name,
              odds: selection.odds
            });
          }
        }
      }
    }
  }
  return rows;
}

function countEvents(sport) {
  return (sport.competitions || []).reduce((total, competition) => total + (competition.events || []).length, 0);
}

function formatMethod(value = "") {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatMoney(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(2) : "0.00";
}

function formatProbability(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(4) : "0.0000";
}

function formatPercent(value) {
  const number = Number(value);
  return `${Number.isFinite(number) ? number.toFixed(2) : "0.00"}%`;
}

createRoot(document.getElementById("root")).render(<App />);
