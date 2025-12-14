// frontend/src/App.jsx
import React, { useEffect, useMemo, useState } from "react";
import {
  getSpecialties,
  getLevels,
  startSession,
  sendChat,
  requestHint,
  getSummary,
  revealObjective,
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
// 70+★ : HIPPOCRATES
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
const LOCAL_PROGRESS_KEY = "agentc_progress_v1";

function clampStars(v) {
  const n = Number(v || 0);
  if (Number.isNaN(n)) return 0;
  return Math.max(0, Math.min(3, n));
}

function loadLocalProgress() {
  try {
    const raw = localStorage.getItem(LOCAL_PROGRESS_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object") return parsed;
    return {};
  } catch {
    return {};
  }
}

function saveLocalProgress(progressObj) {
  try {
    localStorage.setItem(LOCAL_PROGRESS_KEY, JSON.stringify(progressObj || {}));
  } catch {
    // ignore
  }
}

function resetLocalProgress() {
  try {
    localStorage.removeItem(LOCAL_PROGRESS_KEY);
  } catch {
    // ignore
  }
}

// Encode progress into ONE numeric code (base-4 packed into a BigInt, then shown as base-10 digits).
// Order must be stable: missionKeys sorted by specialty then level.
function encodeProgressToCode(progress, missionKeys) {
  if (!missionKeys || missionKeys.length === 0) return "";
  let n = 0n;
  let pow = 1n; // 4^0
  for (let i = 0; i < missionKeys.length; i++) {
    const key = missionKeys[i];
    const digit = BigInt(clampStars(progress?.[key] || 0)); // 0..3
    n += digit * pow;
    pow *= 4n;
  }
  return n.toString(10);
}

function decodeCodeToProgress(codeStr, missionKeys) {
  const cleaned = (codeStr || "").trim();
  if (!/^\d+$/.test(cleaned)) {
    throw new Error("Code must be numbers only.");
  }
  if (!missionKeys || missionKeys.length === 0) {
    throw new Error("Mission map not loaded yet.");
  }

  let n = BigInt(cleaned);
  const out = {};
  for (let i = 0; i < missionKeys.length; i++) {
    const digit = Number(n % 4n); // 0..3
    if (digit > 0) out[missionKeys[i]] = digit;
    n = n / 4n;
  }
  return out;
}

function getRankInfo(totalStarsRaw, globalMaxStarsRaw) {
  const stars = Math.max(0, totalStarsRaw || 0);
  const globalMaxStars = Math.max(1, globalMaxStarsRaw || 1);

  // pick highest tier whose minStars <= stars
  let currentIndex = 0;
  for (let i = 0; i < RANK_TIERS.length; i++) {
    if (stars >= RANK_TIERS[i].minStars) currentIndex = i;
    else break;
  }

  const current = RANK_TIERS[currentIndex];
  const next = RANK_TIERS[currentIndex + 1] || null;

  const currentFloor = current.minStars;
  const nextFloor = next ? next.minStars : globalMaxStars;

  let progressFraction = 0;
  if (!next) {
    const spanToMax = Math.max(1, globalMaxStars - currentFloor);
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

  const [progress, setProgress] = useState(() => loadLocalProgress());
  const [theme, setTheme] = useState("dark");

  // per-level usage
  const [hintsUsed, setHintsUsed] = useState(0);
  const [objectives, setObjectives] = useState([]);
  const [revealsUsed, setRevealsUsed] = useState(0);

  // Boot / loading state
  const [bootStage, setBootStage] = useState("connecting"); // "connecting" | "syncing" | "ready" | "error"
  const [bootMessage, setBootMessage] = useState("Initializing client...");

  // Mission map (stable ordering for restore-code)
  const [missionKeys, setMissionKeys] = useState([]);

  // Restore code UI state
  const [restoreCodeInput, setRestoreCodeInput] = useState("");
  const [restoreStatus, setRestoreStatus] = useState("");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  // Persist local progress whenever it changes
  useEffect(() => {
    saveLocalProgress(progress);
  }, [progress]);

  async function loadInitialData() {
    setError("");
    setBootStage("connecting");
    setBootMessage(`Connecting to mission server at ${API_BASE}...`);

    try {
      // 1) Get specialties
      const specs = await getSpecialties();
      setSpecialties(specs);

      // 2) Build mission map (specialty|level keys) for restore-code stability
      setBootStage("syncing");
      setBootMessage("Loading mission map + local campaign progress...");

      const allLevels = await Promise.all(
        specs.map(async (spec) => {
          const lvls = await getLevels(spec);
          return { spec, lvls: Array.isArray(lvls) ? lvls : [] };
        })
      );

      const keys = [];
      allLevels
        .sort((a, b) => String(a.spec).localeCompare(String(b.spec)))
        .forEach(({ spec, lvls }) => {
          const sortedLvls = [...lvls].sort((x, y) => Number(x) - Number(y));
          sortedLvls.forEach((lvl) => keys.push(`${spec}|${lvl}`));
        });

      setMissionKeys(keys);

      // 3) Local progress already loaded from localStorage (state init)
      setBootStage("ready");
      setBootMessage("Link established. Select a specialty sector to begin.");
    } catch (err) {
      console.error("Initial boot failed", err);
      setError("SYSTEM FAILURE: CONNECTION REFUSED");
      setBootStage("error");
      setBootMessage(
        [
          "Could not reach backend.",
          "",
          "Quick checks:",
          "- Is the backend running and reachable?",
          "- If frontend is on Vercel, make sure API_BASE points to your Render/Flask URL (not localhost).",
          "- On phone: localhost backends on your laptop will NOT work; use the deployed backend URL.",
        ].join("\n")
      );
    }
  }

  useEffect(() => {
    loadInitialData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function toggleTheme() {
    setTheme((prev) => (prev === "light" ? "dark" : "light"));
  }

  async function handleResetData() {
    if (!window.confirm("WARNING: CLEARING LOCAL CAMPAIGN DATA ON THIS DEVICE. CONFIRM?")) return;
    resetLocalProgress();
    setProgress({});
    setRestoreStatus("Local campaign data cleared.");
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
      setHint(`[INTEL RECEIVED] Hint ${data.hint_index}/${data.total_hints}: ${data.hint}`);
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
      setRevealsUsed(typeof data.reveals_used === "number" ? data.reveals_used : revealsUsed + 1);
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

      // Update local progress on THIS device only
      if (session && session.specialty && session.level != null) {
        const key = `${session.specialty}|${session.level}`;
        const earnedStars = clampStars(data.stars || 0);

        setProgress((prev) => {
          const current = clampStars(prev[key] || 0);
          if (earnedStars >= current) {
            const next = { ...prev, [key]: earnedStars };
            // keep storage compact: remove 0-star entries
            if (earnedStars === 0) delete next[key];
            return next;
          }
          return prev;
        });
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

  const totalCompleted = Object.values(progress || {}).filter((v) => (v || 0) > 0).length;
  const totalStars = Object.values(progress || {}).reduce((sum, v) => sum + (v || 0), 0);

  const globalMaxStars = Math.max(1, (missionKeys?.length || 0) * 3);
  const rankInfo = getRankInfo(totalStars, globalMaxStars);

  const starsLeftThisLevel = Math.max(0, MAX_REVEALS_PER_LEVEL - revealsUsed);
  const showBootScreen = bootStage !== "ready";

  const currentSaveCode = useMemo(() => encodeProgressToCode(progress, missionKeys), [progress, missionKeys]);

  async function handleCopySaveCode() {
    try {
      await navigator.clipboard.writeText(currentSaveCode || "");
      setRestoreStatus("Save code copied.");
      setTimeout(() => setRestoreStatus(""), 2000);
    } catch {
      setRestoreStatus("Copy failed. Select the code and copy manually.");
      setTimeout(() => setRestoreStatus(""), 3000);
    }
  }

  function handleRestoreFromCode() {
    setError("");
    setRestoreStatus("");
    try {
      const restored = decodeCodeToProgress(restoreCodeInput, missionKeys);
      setProgress(restored);
      setRestoreStatus("Progress restored on this device.");
      setTimeout(() => setRestoreStatus(""), 2500);
    } catch (e) {
      setRestoreStatus(`Restore failed: ${e.message}`);
      setTimeout(() => setRestoreStatus(""), 3500);
    }
  }

  return (
    <div className="app-root">
      {showBootScreen && (
        <BootScreen stage={bootStage} message={bootMessage} onRetry={bootStage === "error" ? loadInitialData : null} />
      )}

      <div className="scanlines"></div>

      <div className="app-layout">
        <header className="app-header">
          <div className="header-branding">
            <div className="app-logo-box">AG-C</div>
            <div>
              <div className="app-title">AGENT-C SIMULATOR</div>
              <div className="app-subtitle">TACTICAL MEDICAL TRAINING INTERFACE</div>
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
                {rankInfo.nextName ? ` → ${rankInfo.nextName} @ ${rankInfo.nextFloor}★` : " (MAX)"}
              </span>
            </div>

            {session && !showBootScreen && (
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
              <div className="hud-card-header small">CAMPAIGN PROGRESS (DEVICE)</div>

              <div className="status-row small">
                <span className="label">RANK</span>
                <span className="value">{rankInfo.name}</span>
              </div>

              <div className="status-row small">
                <span className="label">STARS</span>
                <span className="value">
                  {totalStars}/{globalMaxStars}
                </span>
              </div>

              <div className="status-row small">
                <span className="label">MISSIONS CLEARED</span>
                <span className="value">
                  {totalCompleted}/{missionKeys.length || 0}
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
                    : `${totalStars} / ${globalMaxStars}★ (MAX RANK)`}
                </div>
              </div>

              <div style={{ marginTop: "15px", textAlign: "center" }}>
                <button className="hud-btn alert small" onClick={handleResetData}>
                  RESET LOCAL DATA
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
                  saveCode={currentSaveCode}
                  restoreCodeInput={restoreCodeInput}
                  onRestoreCodeInput={setRestoreCodeInput}
                  onRestore={handleRestoreFromCode}
                  onCopy={handleCopySaveCode}
                  restoreStatus={restoreStatus}
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
              {step === "specialty" ? "SELECT SPEC" : step === "level" ? "SELECT DIFF" : "ACTIVE"}
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
            <span className="tag tech">{session.specialty.substring(0, 3).toUpperCase()}</span>
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

function SpecialtyScreen({
  specialties,
  onSelect,
  saveCode,
  restoreCodeInput,
  onRestoreCodeInput,
  onRestore,
  onCopy,
  restoreStatus,
}) {
  return (
    <div className="screen-container">
      <div className="screen-header">
        <h2 className="screen-title">SELECT SPECIALTY SECTOR</h2>
        <p className="screen-subtitle">Identify training module to commence.</p>
      </div>

      <div className="hud-card savecode-card">
        <div className="hud-card-header small">SAVE / RESTORE (NUMERIC CODE)</div>

        <div className="savecode-row">
          <div className="savecode-label">YOUR SAVE CODE</div>
          <div className="savecode-code">{saveCode || "0"}</div>
        </div>

        <div className="savecode-actions">
          <button type="button" className="hud-btn secondary small" onClick={onCopy} disabled={!saveCode}>
            COPY
          </button>
        </div>

        <div className="savecode-divider"></div>

        <div className="savecode-row">
          <div className="savecode-label">RESTORE CODE</div>
          <input
            type="text"
            className="hud-input savecode-input"
            placeholder="Paste / type a numeric code to restore"
            value={restoreCodeInput}
            onChange={(e) => onRestoreCodeInput(e.target.value)}
          />
        </div>

        <div className="savecode-actions">
          <button type="button" className="hud-btn primary small" onClick={onRestore} disabled={!restoreCodeInput.trim()}>
            RESTORE
          </button>
        </div>

        {restoreStatus && <div className="savecode-status">{restoreStatus}</div>}
        <div className="savecode-note">
          Tip: This is device-local progress. It will not auto-sync to other devices unless you restore the same code.
        </div>
      </div>

      <div className="grid" style={{ marginTop: "15px" }}>
        {specialties.map((spec) => (
          <button key={spec} className="game-card-btn" onClick={() => onSelect(spec)}>
            <div className="card-deco"></div>
            <div className="card-content">
              <div className="card-title">{spec.toUpperCase()}</div>
              <div className="card-subtitle">MODULES AVAILABLE</div>
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
          <h2 className="screen-title">SECTOR: {specialty ? specialty.toUpperCase() : "UNKNOWN"}</h2>
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
              Reveals: {revealsUsed}/{MAX_REVEALS_PER_LEVEL} · Stars left: {starsLeftThisLevel}
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
                    <span className="objective-type">{obj.type === "diagnosis" ? "DX" : "TX"}</span>
                    <span className="objective-label">{obj.visible ? obj.label : "????"}</span>
                  </div>
                );
              })
            ) : (
              <span className="objective-helper">Objectives will light up as you discover them.</span>
            )}
          </div>
          <div className="objective-meta">
            <span className="chip">PLAN: clarify → risk factors → diagnose → treat</span>
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
            {messages.length === 0 && <div className="chat-empty">AWAITING INPUT...</div>}
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
          <button type="submit" className="hud-btn primary" disabled={loading || !input.trim()}>
            TRANSMIT
          </button>
        </form>

        <div className="chat-actions">
          <button className="hud-btn secondary" onClick={onHint} disabled={hintLoading || missionComplete}>
            {hintLoading ? "SCANNING..." : "INTEL HINT"}
          </button>

          <button
            className="hud-btn secondary"
            onClick={onReveal}
            disabled={revealLoading || missionComplete || starsLeftThisLevel <= 0 || !hasHiddenObjectives}
          >
            {revealLoading
              ? "REVEALING..."
              : starsLeftThisLevel <= 0
              ? "NO STARS LEFT"
              : !hasHiddenObjectives
              ? "NO OBJECTIVES LEFT"
              : "REVEAL OBJ (-1★)"}
          </button>

          <button className="hud-btn alert" onClick={onSummary} disabled={summaryLoading}>
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

function BootScreen({ stage, message, onRetry }) {
  const isError = stage === "error";

  const statusText =
    stage === "ready"
      ? "ONLINE"
      : stage === "error"
      ? "OFFLINE – BACKEND UNREACHABLE"
      : stage === "syncing"
      ? "LOADING LOCAL PROGRESS + MISSION MAP..."
      : "CONNECTING TO BACKEND...";

  return (
    <div className="boot-screen">
      <div className="boot-panel">
        <div className="boot-title">AGENT-C BOOT SEQUENCE</div>
        <div className="boot-status-line">{statusText}</div>

        <div className="boot-log">
          <div className="boot-step">[1/3] Connect to backend ({API_BASE})</div>
          <div className="boot-step">[2/3] Load mission map</div>
          <div className="boot-step">[3/3] Load local campaign progress</div>
        </div>

        <pre className="boot-message">{message}</pre>

        {isError && onRetry && (
          <button type="button" className="hud-btn alert small" onClick={onRetry}>
            RETRY CONNECTION
          </button>
        )}
      </div>
    </div>
  );
}

export default App;
