// frontend/src/App.jsx
import React, { useEffect, useState } from "react";
import {
  getSpecialties,
  getLevels,
  startSession,
  sendChat,
  requestHint,
  getSummary,
  revealObjective,
  getProgress as apiGetProgress,
  resetProgress as apiResetProgress,
} from "./api";
import { API_BASE } from "./config";

// --- Rank System ---
// 0–9★ : STUDENT
// 10–19★ : INTERN
// 20–29★ : RESIDENT
// 30–39★ : FELLOW
// 40–49★ : ATTENDING
// 50–59★ : CHIEF
// 60–69★ : LEGEND
// 70–75★ : HIPPOCRATES
const RANK_TIERS = [
  { name: "STUDENT", minStars: 0 },
  { name: "INTERN", minStars: 10 },
  { name: "RESIDENT", minStars: 20 },
  { name: "FELLOW", minStars: 30 },
  { name: "ATTENDING", minStars: 40 },
  { name: "CHIEF", minStars: 50 },
  { name: "LEGEND", minStars: 60 },
  { name: "HIPPOCRATES", minStars: 70 },
];

const MAX_REVEALS_PER_LEVEL = 3;
const TOTAL_LEVELS = 25;
const GLOBAL_MAX_STARS = TOTAL_LEVELS * 3;

function getRankInfo(totalStarsRaw) {
  const stars = Math.max(0, totalStarsRaw || 0);

  // pick highest tier whose minStars <= stars
  let currentIndex = 0;
  for (let i = 0; i < RANK_TIERS.length; i++) {
    if (stars >= RANK_TIERS[i].minStars) {
      currentIndex = i;
    } else {
      break;
    }
  }

  const current = RANK_TIERS[currentIndex];
  const next = RANK_TIERS[currentIndex + 1] || null;

  const currentFloor = current.minStars;
  const nextFloor = next ? next.minStars : GLOBAL_MAX_STARS;

  let progressFraction = 0;
  if (!next) {
    const spanToMax = Math.max(1, GLOBAL_MAX_STARS - currentFloor);
    progressFraction = Math.min(1, (stars - currentFloor) / spanToMax);
  } else {
    const span = Math.max(1, nextFloor - currentFloor);
    progressFraction = Math.min(1, (stars - currentFloor) / span);
  }

  const progressPercent = Math.round(progressFraction * 100);

  return {
    name: current.name,
    currentFloor,
    nextName: next ? next.name : null,
    nextFloor,
    progressPercent,
  };
}

// --- Utility Functions for global progress ---
// (These just wrap the API helpers; kept here for clarity)

async function fetchGlobalProgress() {
  try {
    const data = await apiGetProgress();
    return data;
  } catch (e) {
    console.error("Failed to fetch progress", e);
    return { progress: {} };
  }
}

async function resetGlobalProgress() {
  try {
    const data = await apiResetProgress();
    return data;
  } catch (e) {
    console.error("Failed to reset progress", e);
    return { progress: {} };
  }
}

// --- Main Component ---

function App() {
  const [step, setStep] = useState("specialty"); // "specialty" | "level" | "chat"
  const [specialties, setSpecialties] = useState([]);
  const [levels, setLevels] = useState([]);
  const [selectedSpecialty, setSelectedSpecialty] = useState("");
  const [selectedLevel, setSelectedLevel] = useState(null);

  const [session, setSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");

  const [loading, setLoading] = useState(false);
  const [hintLoading, setHintLoading] = useState(false);
  const [revealLoading, setRevealLoading] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);

  const [hint, setHint] = useState("");
  const [summary, setSummaryState] = useState(null);
  const [error, setError] = useState("");

  const [progress, setProgress] = useState({});
  const [theme, setTheme] = useState("dark");

  // per-level usage
  const [hintsUsed, setHintsUsed] = useState(0);
  const [objectives, setObjectives] = useState([]);
  const [revealsUsed, setRevealsUsed] = useState(0);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  // Initial Load: Specialties + Progress
  useEffect(() => {
    async function load() {
      try {
        const [specs, progData] = await Promise.all([
          getSpecialties(),
          fetchGlobalProgress(),
        ]);
        setSpecialties(specs);
        if (progData.progress) {
          setProgress(progData.progress);
        }
      } catch (err) {
        console.error(err);
        setError("SYSTEM FAILURE: CONNECTION REFUSED");
      }
    }
    load();
  }, []);

  function toggleTheme() {
    setTheme((prev) => (prev === "light" ? "dark" : "light"));
  }

  // --- Reset Handler ---
  async function handleResetData() {
    if (!window.confirm("WARNING: CLEARING ALL CAMPAIGN DATA. CONFIRM?")) return;
    try {
      const data = await resetGlobalProgress();
      setProgress(data.progress || {});
    } catch (err) {
      console.error(err);
      setError("RESET FAILED");
    }
  }

  async function handleSpecialtyClick(spec) {
  setSelectedSpecialty(spec);
  setSelectedLevel(null);
  setError("");
  setLevels([]);
  setHint("");
  setSummaryState(null);
  setMessages([]);
  setSession(null);
  setHintsUsed(0);
  setObjectives([]);
  setRevealsUsed(0);

  // THIS LINE WAS MISSING
  setStep("level");

  try {
    const data = await getLevels(spec);
    setLevels(data);
  } catch (err) {
    console.error(err);
    setError("SYSTEM FAILURE: SECTOR LOCKED");
  }
}


  async function handleLevelClick(level) {
    setSelectedLevel(level);
    setError("");
    setHint("");
    setSummaryState(null);
    setMessages([]);
    setHintsUsed(0);
    setObjectives([]);
    setRevealsUsed(0);
    setLoading(true);

    try {
      const data = await startSession({
        specialty: selectedSpecialty,
        level,
      });

      setSession(data);
      setStep("chat");
      setObjectives(data.objectives || []);

      const introMsg = {
        role: "system",
        content: `INCOMING TRANSMISSION...\nPATIENT: ${data.patient_name}\nCOMPLAINT: ${data.chief_complaint}\n\nMISSION: DIAGNOSE AND TREAT.`,
      };
      setMessages([introMsg]);
    } catch (err) {
      console.error(err);
      setError("CONNECTION ERROR: RETRY");
    } finally {
      setLoading(false);
    }
  }

  async function handleSend(e) {
    e.preventDefault();
    if (!session || !input.trim() || loading) return;

    const text = input.trim();
    setInput("");
    setError("");
    setHint("");
    setLoading(true);

    try {
      const data = await sendChat({
        sessionId: session.session_id,
        message: text,
      });

      setMessages((prev) => [
        ...prev,
        { role: "user", content: text },
        { role: "assistant", content: data.reply },
      ]);

      if (Array.isArray(data.objectives)) {
        setObjectives(data.objectives);
      }

      if (data.done || data.accepted_treatment !== undefined) {
        setSession((prev) =>
          prev
            ? {
                ...prev,
                done: data.done,
                accepted_treatment: data.accepted_treatment,
              }
            : prev
        );
      }
    } catch (err) {
      console.error(err);
      setError("TRANSMISSION FAILED");
    } finally {
      setLoading(false);
    }
  }

  // Hints: textual intel (efficiency penalty, not star spend)
  async function handleHint() {
    if (!session || hintLoading) return;

    setError("");
    setHintLoading(true);
    try {
      const data = await requestHint({ sessionId: session.session_id });
      setHint(
        `[INTEL RECEIVED] Hint ${data.hint_index}/${data.total_hints}: ${data.hint}`
      );
      setHintsUsed((prev) => prev + 1);
    } catch (err) {
      console.error(err);
      setError("INTEL UNAVAILABLE");
    } finally {
      setHintLoading(false);
    }
  }

  // Reveal: flips one hidden objective visible (and marks achieved) at cost of 1 star
  async function handleReveal() {
    if (!session || revealLoading) return;

    const hasHidden = (objectives || []).some((o) => !o.visible);
    if (!hasHidden) {
      setError("NO HIDDEN OBJECTIVES LEFT TO REVEAL");
      return;
    }

    if (revealsUsed >= MAX_REVEALS_PER_LEVEL) {
      setError("NO STARS LEFT TO SPEND ON REVEALS");
      return;
    }

    setError("");
    setRevealLoading(true);
    try {
      const data = await revealObjective({ sessionId: session.session_id });
      if (Array.isArray(data.objectives)) {
        setObjectives(data.objectives);
      }
      setRevealsUsed(
        typeof data.reveals_used === "number"
          ? data.reveals_used
          : revealsUsed + 1
      );
      setHint(`[OBJECTIVE REVEALED] ${data.message}`);
    } catch (err) {
      console.error(err);
      setError("REVEAL FAILED");
    } finally {
      setRevealLoading(false);
    }
  }

  async function handleSummary() {
    if (!session || summaryLoading) return;
    setError("");
    setSummaryLoading(true);
    try {
      const data = await getSummary(session.session_id);
      setSummaryState(data);

      // Update local progress instantly if this run was better
      if (session && session.specialty && session.level != null) {
        const key = `${session.specialty}|${session.level}`;
        const earnedStars = data.stars || 0;

        setProgress((prev) => {
          const current = prev[key] || 0;
          if (earnedStars >= current) {
            return { ...prev, [key]: earnedStars };
          }
          return prev;
        });
      }

      // Double check sync with backend
      const progData = await fetchGlobalProgress();
      if (progData.progress) {
        setProgress((prev) => ({ ...prev, ...progData.progress }));
      }

      // Sync revealsUsed from backend summary if available
      if (typeof data.reveals_used === "number") {
        setRevealsUsed(data.reveals_used);
      }
    } catch (err) {
      console.error(err);
      setError("DEBRIEF FAILED");
    } finally {
      setSummaryLoading(false);
    }
  }

  function handleNewCase() {
    setStep("specialty");
    setSelectedSpecialty("");
    setSelectedLevel(null);
    setSession(null);
    setMessages([]);
    setHint("");
    setSummaryState(null);
    setHintsUsed(0);
    setObjectives([]);
    setRevealsUsed(0);
    setError("");
  }

  function handleBackToSpecialty() {
    setStep("specialty");
    setSession(null);
    setMessages([]);
    setHint("");
    setSummaryState(null);
    setHintsUsed(0);
    setObjectives([]);
    setRevealsUsed(0);
    setError("");
    setSelectedLevel(null);
    setSelectedSpecialty("");
  }

  function handleBackToLevel() {
    if (!selectedSpecialty) {
      setStep("specialty");
      return;
    }
    setStep("level");
    setSession(null);
    setMessages([]);
    setHint("");
    setSummaryState(null);
    setHintsUsed(0);
    setObjectives([]);
    setRevealsUsed(0);
    setError("");
    setSelectedLevel(null);
  }

  const totalCompleted = Object.keys(progress).length;

  const totalStars = Object.values(progress || {}).reduce(
    (sum, v) => sum + (v || 0),
    0
  );
  const rankInfo = getRankInfo(totalStars);

  const starsLeftThisLevel = Math.max(
    0,
    MAX_REVEALS_PER_LEVEL - revealsUsed
  );

  return (
    <div className="app-root">
      <div className="scanlines"></div>
      <div className="app-layout">
        <header className="app-header">
          <div className="header-branding">
            <div className="app-logo-box">AG-C</div>
            <div>
              <div className="app-title">AGENT-C SIMULATOR</div>
              <div className="app-subtitle">
                TACTICAL MEDICAL TRAINING INTERFACE
              </div>
            </div>
          </div>
          <div className="header-right">
            <button type="button" className="hud-btn small" onClick={toggleTheme}>
              {theme === "light" ? "☾ NIGHT" : "☀ DAY"}
            </button>
            <div className="rank-display">
              <span className="rank-label">CURRENT RANK</span>
              <span className="rank-value">{rankInfo.name}</span>
              <span className="rank-stars">
                {totalStars}★
                {rankInfo.nextName
                  ? ` → ${rankInfo.nextName} @ ${rankInfo.nextFloor}★`
                  : " (MAX)"}
              </span>
            </div>
            {session && (
              <button className="hud-btn alert small" onClick={handleNewCase}>
                ABORT / NEW
              </button>
            )}
          </div>
        </header>

        <main className="app-main">
          <div className="left-panel">
            <GameInfo
              step={step}
              session={session}
              selectedSpecialty={selectedSpecialty}
              selectedLevel={selectedLevel}
              summary={summary}
            />

            <div className="hud-card info-card campaign-panel">
              <div className="hud-card-header small">CAMPAIGN PROGRESS</div>
              <div className="status-row small">
                <span className="label">RANK</span>
                <span className="value">{rankInfo.name}</span>
              </div>
              <div className="status-row small">
                <span className="label">STARS</span>
                <span className="value">{totalStars}/{GLOBAL_MAX_STARS}</span>
              </div>
              <div className="status-row small">
                <span className="label">MISSIONS CLEARED</span>
                <span className="value">
                  {totalCompleted}/{TOTAL_LEVELS}
                </span>
              </div>
              <div className="xp-container">
                <div className="xp-bar">
                  <div
                    className="xp-fill"
                    style={{
                      width: `${rankInfo.progressPercent}%`,
                      background: "var(--success)",
                    }}
                  ></div>
                </div>
                <div className="xp-label">
                  {rankInfo.nextName
                    ? `${totalStars} / ${rankInfo.nextFloor}★ to ${rankInfo.nextName}`
                    : `${totalStars} / ${GLOBAL_MAX_STARS}★ (MAX RANK)`}
                </div>
              </div>
              <div style={{ marginTop: "15px", textAlign: "center" }}>
                <button className="hud-btn alert small" onClick={handleResetData}>
                  RESET DATA
                </button>
              </div>
            </div>

            {error && <div className="error-banner">⚠ ALERT: {error}</div>}
          </div>

          <div className="right-panel">
            <div className="content-frame">
              {step === "specialty" && (
                <SpecialtyScreen
                  specialties={specialties}
                  onSelect={handleSpecialtyClick}
                />
              )}

              {step === "level" && (
                <LevelScreen
                  specialty={selectedSpecialty}
                  levels={levels}
                  loading={loading}
                  onBack={() => setStep("specialty")}
                  onSelectLevel={handleLevelClick}
                  progress={progress}
                />
              )}

              {step === "chat" && session && (
                <ChatScreen
                  session={session}
                  messages={messages}
                  input={input}
                  loading={loading}
                  hint={hint}
                  hintLoading={hintLoading}
                  revealLoading={revealLoading}
                  summary={summary}
                  summaryLoading={summaryLoading}
                  hintsUsed={hintsUsed}
                  objectives={objectives}
                  revealsUsed={revealsUsed}
                  starsLeftThisLevel={starsLeftThisLevel}
                  onInputChange={setInput}
                  onSend={handleSend}
                  onHint={handleHint}
                  onReveal={handleReveal}
                  onSummary={handleSummary}
                  onBackToSpecialty={handleBackToSpecialty}
                  onBackToLevel={handleBackToLevel}
                />
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

function GameInfo({ step, session, selectedSpecialty, selectedLevel, summary }) {
  return (
    <div className="hud-card info-card">
      <div className="hud-card-header">MISSION STATUS</div>

      {!session && (
        <div className="status-grid">
          <div className="status-row">
            <span className="label">PHASE</span>
            <span className="value blink">
              {step === "specialty"
                ? "SELECT SPEC"
                : step === "level"
                ? "SELECT DIFF"
                : "ACTIVE"}
            </span>
          </div>
          {selectedSpecialty && (
            <div className="status-row">
              <span className="label">SECTOR</span>
              <span className="value">{selectedSpecialty.toUpperCase()}</span>
            </div>
          )}
          {selectedLevel && (
            <div className="status-row">
              <span className="label">LEVEL</span>
              <span className="value">{selectedLevel}</span>
            </div>
          )}
        </div>
      )}

      {session && (
        <div className="active-mission-stats">
          <div className="mission-tags">
            <span className="tag tech">
              {session.specialty.substring(0, 3).toUpperCase()}
            </span>
            <span className="tag warning">LVL {session.level}</span>
          </div>
          <div className="patient-file">
            <div className="file-label">PATIENT ID</div>
            <div className="file-name">{session.patient_name}</div>
            <div className="file-label">CHIEF COMPLAINT</div>
            <div className="file-complaint">{session.chief_complaint}</div>
          </div>
        </div>
      )}

      {summary && (
        <div className="summary-preview">
          <div className="hud-card-header small">LAST OPERATION</div>
          <div className="status-row small">
            <span className="label">RATING</span>
            <StarRow stars={summary.stars} />
          </div>
          <div className="status-row small">
            <span className="label">DX</span>
            <span className="value">{summary.diagnosis}</span>
          </div>
        </div>
      )}
    </div>
  );
}

function SpecialtyScreen({ specialties, onSelect }) {
  return (
    <div className="screen-container">
      <div className="screen-header">
        <h2 className="screen-title">SELECT SPECIALTY SECTOR</h2>
        <p className="screen-subtitle">Identify training module to commence.</p>
      </div>
      <div className="grid">
        {specialties.map((spec) => (
          <button key={spec} className="game-card-btn" onClick={() => onSelect(spec)}>
            <div className="card-deco"></div>
            <div className="card-content">
              <div className="card-title">{spec.toUpperCase()}</div>
              <div className="card-subtitle">5 MODULES AVAILABLE</div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function LevelScreen({ specialty, levels, loading, onBack, onSelectLevel, progress }) {
  return (
    <div className="screen-container">
      <div className="screen-header row">
        <button className="hud-btn small" onClick={onBack}>
          &lt; BACK
        </button>
        <div>
          <h2 className="screen-title">
            SECTOR: {specialty ? specialty.toUpperCase() : "UNKNOWN"}
          </h2>
          <p className="screen-subtitle">Select simulation difficulty.</p>
        </div>
      </div>

      {loading && <div className="loading-text blink">INITIALIZING SIMULATION...</div>}

      <div className="grid">
        {levels.map((level) => {
          let badgeClass = "badge-medium";
          let diffText = "STD";
          if (level <= 2) {
            badgeClass = "badge-easy";
            diffText = "BAS";
          }
          if (level >= 4) {
            badgeClass = "badge-hard";
            diffText = "ADV";
          }

          const key = `${specialty}|${level}`;
          const stars = progress[key];

          return (
            <button
              key={level}
              className={`game-card-btn level ${stars ? "completed" : ""}`}
              onClick={() => onSelectLevel(level)}
            >
              <div className="level-number">{level}</div>
              <div className="card-content">
                <div className="level-header">
                  <span className={`badge ${badgeClass}`}>{diffText}</span>
                  <div className="card-title">SIMULATION {level}</div>
                </div>
                {stars !== undefined && (
                  <div className="level-stars">
                    {"★".repeat(stars)}
                    <span className="dim">{"★".repeat(3 - stars)}</span>
                  </div>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function ChatScreen({
  session,
  messages,
  input,
  loading,
  hint,
  hintLoading,
  revealLoading,
  summary,
  summaryLoading,
  hintsUsed,
  objectives,
  revealsUsed,
  starsLeftThisLevel,
  onInputChange,
  onSend,
  onHint,
  onReveal,
  onSummary,
  onBackToSpecialty,
  onBackToLevel,
}) {
  const missionComplete = !!summary;
  const hasHiddenObjectives = (objectives || []).some((o) => !o.visible);

  return (
    <div className="chat-layout">
      <div className="hud-card chat-card">
        <div className="chat-header">
          <div className="chat-title-group">
            <div className="led-indicator active"></div>
            <div>
              <div className="chat-title">LIVE FEED</div>
              <div className="chat-subtitle">SECURE CONNECTION ESTABLISHED</div>
            </div>
          </div>
          <div className="chat-controls">
            <button className="hud-btn small" onClick={onBackToLevel}>
              LEVELS
            </button>
            <button className="hud-btn small" onClick={onBackToSpecialty}>
              SECTORS
            </button>
          </div>
        </div>

        <div className="chat-objectives">
          <div className="objectives-header">
            <span>CASE OBJECTIVES</span>
            <span className="objective-helper">
              Reveals: {revealsUsed}/{MAX_REVEALS_PER_LEVEL} · Stars left:{" "}
              {starsLeftThisLevel}
            </span>
          </div>
          <div className="objective-pill-row">
            {objectives && objectives.length > 0 ? (
              objectives.map((obj) => {
                let cls = "objective-pill";
                if (!obj.visible) cls += " hidden";
                if (obj.achieved) cls += " achieved";
                if (obj.revealed_by_user) cls += " revealed";
                return (
                  <div key={obj.id} className={cls}>
                    <span className="objective-type">
                      {obj.type === "diagnosis" ? "DX" : "TX"}
                    </span>
                    <span className="objective-label">
                      {obj.visible ? obj.label : "????"}
                    </span>
                  </div>
                );
              })
            ) : (
              <span className="objective-helper">
                Objectives will light up as you discover them.
              </span>
            )}
          </div>
          <div className="objective-meta">
            <span className="chip">
              PLAN: clarify → risk factors → diagnose → treat
            </span>
          </div>
        </div>

        <div className="hint-meta-row">
          <span>Hints used: {hintsUsed}</span>
          <span>
            Reveals: {revealsUsed}/{MAX_REVEALS_PER_LEVEL}
          </span>
        </div>

        <div className="chat-window">
          <div className="chat-messages-container">
            {messages.length === 0 && (
              <div className="chat-empty">AWAITING INPUT...</div>
            )}
            {messages.map((m, idx) => (
              <MessageBubble key={idx} role={m.role} content={m.content} />
            ))}
            {loading && <div className="chat-loading blink">PATIENT TYPING...</div>}
          </div>
        </div>

        <form className="chat-input-row" onSubmit={onSend}>
          <input
            type="text"
            className="hud-input"
            placeholder="ENTER COMMAND / QUESTION..."
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
          />
          <button
            type="submit"
            className="hud-btn primary"
            disabled={loading || !input.trim()}
          >
            TRANSMIT
          </button>
        </form>

        <div className="chat-actions">
          <button
            className="hud-btn secondary"
            onClick={onHint}
            disabled={hintLoading || missionComplete}
          >
            {hintLoading ? "SCANNING..." : "INTEL HINT"}
          </button>
          <button
            className="hud-btn secondary"
            onClick={onReveal}
            disabled={
              revealLoading ||
              missionComplete ||
              starsLeftThisLevel <= 0 ||
              !hasHiddenObjectives
            }
          >
            {revealLoading
              ? "REVEALING..."
              : starsLeftThisLevel <= 0
              ? "NO STARS LEFT"
              : !hasHiddenObjectives
              ? "NO OBJECTIVES LEFT"
              : "REVEAL OBJ (-1★)"}
          </button>
          <button
            className="hud-btn alert"
            onClick={onSummary}
            disabled={summaryLoading}
          >
            {summaryLoading ? "ANALYZING..." : "END MISSION"}
          </button>
        </div>

        {hint && <div className="hint-box type-writer">{hint}</div>}
      </div>

      {summary && <SummaryPanel summary={summary} />}
    </div>
  );
}

function MessageBubble({ role, content }) {
  if (role === "system") {
    return (
      <div className="msg-row system">
        <div className="msg-content system-content">{content}</div>
      </div>
    );
  }
  const isDoctor = role === "user";
  return (
    <div className={`msg-row ${isDoctor ? "doctor" : "patient"}`}>
      <div className="msg-avatar">{isDoctor ? "DR" : "PT"}</div>
      <div className="msg-bubble">
        <div className="msg-content">{content}</div>
      </div>
    </div>
  );
}

function StarRow({ stars }) {
  return (
    <div className="star-row">
      {[1, 2, 3].map((i) => (
        <span key={i} className={`game-star ${i <= stars ? "filled" : "empty"}`}>
          ★
        </span>
      ))}
    </div>
  );
}

function MetricBar({ label, value, color }) {
  return (
    <div className="metric-row">
      <div className="metric-header">
        <span className="metric-label">{label}</span>
        <span className="metric-val">{value}%</span>
      </div>
      <div className="xp-bar" style={{ height: "4px", background: "#333" }}>
        <div
          className="xp-fill"
          style={{
            width: `${value}%`,
            background: color,
            boxShadow: `0 0 8px ${color}`,
          }}
        ></div>
      </div>
    </div>
  );
}

function SummaryPanel({ summary }) {
  const acc = summary.score_accuracy || 0;
  const th = summary.score_thoroughness || 0;
  const eff = summary.score_efficiency || 0;
  const avg = Math.round((acc + th + eff) / 3);

  return (
    <div className="hud-card summary-card">
      <div className="hud-card-header">MISSION DEBRIEF</div>

      <div className="score-display">
        <div className="big-score">{avg}</div>
        <div className="score-label">OVERALL RATING</div>
        <StarRow stars={summary.stars} />
      </div>

      <div className="metrics-grid">
        <MetricBar label="ACCURACY" value={acc} color="var(--primary)" />
        <MetricBar label="INTEL/DATA" value={th} color="var(--secondary)" />
        <MetricBar label="SPEED/EFF" value={eff} color="var(--warning)" />
      </div>

      <div className="metrics-meta">
        <div className="status-row small">
          <span className="label">Hints used</span>
          <span className="value">{summary.hints_used}</span>
        </div>
        <div className="status-row small">
          <span className="label">Objectives revealed</span>
          <span className="value">{summary.reveals_used}</span>
        </div>
      </div>

      <div className="terminal-text">{summary.feedback}</div>
      <div className="summary-footer">SIMULATION COMPLETE. DATA LOGGED.</div>
    </div>
  );
}

export default App;
