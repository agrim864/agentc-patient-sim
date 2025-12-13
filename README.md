# AGENT-C: Interactive Clinical Reasoning Simulator

AGENT-C is a gamified clinical reasoning trainer:

* You play as the doctor (operator).
* A simulated patient chats back, powered by an LLM and LangGraph.
* You work through staged clinical cases, make a diagnosis (DX), propose treatment (TX), and then receive a detailed debrief with stars, scores, and rank progression.

This README documents:

* What the system does (mechanics and rules)
* How the backend and frontend are structured
* All the small UX rules: hints, reveals, star math, rank system, spelling tolerance, etc.
* How to run and extend it

---

## 1. Tech stack

Backend

* Python
* Flask
* LangGraph (conversation state machine)
* Google Gemini via `langchain_google_genai`
* Simple in-memory storage for sessions and progress

Frontend

* React (single page)
* Custom CSS HUD look (dark/light theme, rank bar, scanlines)
* Simple API wrapper in `src/api.js`

---

## 2. High-level gameplay loop

1. Choose a specialty sector
   From `/api/specialties` (Neurology, etc.).

2. Choose a level
   Using `/api/levels?specialty=...`. Each level is a different patient case.

3. Start session
   Frontend calls `/api/start-session` with your chosen specialty and level. Backend:

   * Picks a case (`pick_case` from `patient_cases.py`).
   * Creates a session id.
   * Sets up the patient state machine and hidden objectives (DX + key TX items).
   * Returns patient demographics, chief complaint, and max stages.

4. Chat with the patient

   * You type questions or share your thought process.
   * The patient responds in a realistic way using Gemini via LangGraph.
   * The system tries to detect:

     * When you have basically named the correct diagnosis.
     * When you are proposing concrete treatment steps.

5. Use tools (hints and reveals as implemented)

   * Hint button: calls `/api/hint` and shows a textual hint.
   * DX/TX reveal (conceptual): reveals checklist items for diagnosis or treatments.
   * Both affect stars, but in slightly different ways (explained in detail below).

6. End mission and debrief

   * When you are done, click “END MISSION”.
   * Backend `/api/summary/:session_id` calculates your stars and scores and updates global progress.
   * You see:

     * Stars (0–3) for this level
     * Numeric scores: accuracy / thoroughness / efficiency
     * After-action feedback and notes
     * Your global rank and rank progress move accordingly.

---

## 3. Backend architecture

Main files:

* `backend/app.py`
  Flask app, REST endpoints, heuristics, scoring, progress.
* `backend/graph.py`
  LangGraph state machine + LLM evaluator + patient simulator.
* `backend/models.py`
  Pydantic models for request/response payloads and logging.

### 3.1 In-memory stores

`app.py` keeps simple in-memory dicts:

* `USER_PROGRESS: Dict[str, int]`
  Key: `"specialty|level"`
  Value: best stars earned so far for that level (0–3).

* `SESSION_CASES: Dict[str, dict]`
  Maps `session_id` to the selected case dict.

* `SESSION_LOGS: Dict[str, LogEntry]`
  Log per session: turns, hints, stars, scores, etc.

* `SESSION_STATES: Dict[str, PatientState]`
  Full LangGraph state including messages, stage, metrics, objectives, etc.

These reset when the backend restarts (no DB yet).

### 3.2 PatientState (conversation state)

Defined in `graph.py`:

```python
class PatientState(TypedDict, total=False):
    messages: Annotated[List[BaseMessage], operator.add]
    case: Dict[str, Any]
    stage: int
    accepted_treatment: bool
    done: bool
    final_diagnosis: str
    final_feedback: str
    hints_used: int
    score_accuracy: int
    score_thoroughness: int
    score_efficiency: int
    diagnosis_correct: bool
    treatment_hits: int
    objectives: List[Dict[str, Any]]
    reveals_used: int
```

Key ideas:

* `messages` holds the whole multi-turn chat (doctor and patient).
* `stage` controls how much of the case is revealed.
* `objectives` is the DX/TX checklist.
* `hints_used` and `reveals_used` are used for scoring and rank effects.

---

## 4. Case and stage design

Each case in `patient_cases.py` has:

* Basic data: `id`, `name`, `age`, `gender`, `chief_complaint`, `specialty`, `level`, `difficulty`.
* True answer: `expected_diagnosis`.
* Optional: `diagnosis_keywords` to help match synonyms.
* Treatment keys:

  * `treatment_keywords` or `expected_treatment_keywords`
    Used to detect if you are proposing the right treatment steps.
* `stages`: list of symptom chunks. As `stage` increases, more entries from this list are exposed to the patient simulation.
* `hints`: list of hints you can request.

The stage progression is linear: each time you talk to the patient (and the evaluator does not close the case), the `stage` increments until it hits `max_stage`.

---

## 5. Objectives system (DX / TX checklist)

Hidden objectives are built when you start a session:

```python
def _build_objectives_for_case(case: dict) -> List[Dict[str, Any]]:
    # 1 diagnosis objective
    # 0+ treatment objectives
```

For each case:

1. Diagnosis objective

* Created from `expected_diagnosis`.
* Fields:

  ```python
  {
    "id": "diagnosis",
    "label": expected_dx,
    "type": "diagnosis",
    "visible": False,
    "achieved": False,
    "revealed_by_user": False,
    "keywords": [expected_dx],
  }
  ```

2. Treatment objectives

* One objective per item in `treatment_keywords` / `expected_treatment_keywords`.

3. Objectives in API

* We never send the `keywords` field to the frontend.
* Frontend sees:

  ```json
  {
    "id": "treatment_0",
    "label": "Start IV alteplase within appropriate window",
    "type": "treatment",
    "visible": false,
    "achieved": false,
    "revealed_by_user": false
  }
  ```

4. Auto-unlocking objectives (spelling tolerant)

Whenever the user sends a message, `_update_objectives_from_message` runs:

* It checks each hidden objective’s keywords against the latest text.
* If your text is “basically” the same (including minor spelling mistakes), that objective becomes:

  * `achieved = True`
  * `visible = True`

So the checklist fills itself in as you reason through the case, even if your spelling is not perfect.

---

## 6. Spelling tolerance / “misspelling manager”

To avoid punishing minor spelling mistakes, the backend uses fuzzy matching with `difflib.SequenceMatcher`.

High-level behavior:

* Diagnoses
  If your message overlaps strongly with the diagnosis keyword tokens (even with small typos), it counts as a correct diagnosis.
* Treatments
  If you describe a treatment objective with slight spelling errors, it still counts as a treatment hit.
* Objectives
  Checklist auto-update uses the same fuzzy logic.

Core helpers (conceptual):

```python
def _fuzzy_token_match(a, b, threshold=0.8):
    # Returns True if a and b are similar enough (ratio >= 0.8)

def _phrase_hit(text, phrase, min_tokens=1):
    # Break both into tokens, count how many phrase tokens have a close match
    # in the text tokens (allowing typos)
    # Return True if enough tokens match.

def _token_overlap_match(text, target_phrases, min_overlap=1):
    # Diagnosis detection: any phrase that passes _phrase_hit is a match.

def _count_keyword_hits(text, keywords):
    # Treatment detection: counts how many treatment phrases match via _phrase_hit.

def _update_objectives_from_message(state, msg):
    # Marks objectives as achieved if msg hits their keyword phrases via _phrase_hit.
```

Examples of what should now be recognized:

* “ischemic strok” ≈ “ischemic stroke”
* “thrombyltic therapy” ≈ “thrombolytic therapy”
* “metropolol” ≈ “metoprolol”

As long as the strings are close enough, the detection logic still fires.

---

## 7. Diagnosis and treatment detection

There are two paths that can complete a case:

1. Heuristic path in `app.py`
2. LLM evaluator path in `graph.py`

### 7.1 Heuristic rules (fast path)

In `/api/chat`:

1. Detect diagnosis

   * `diag_keywords` is taken from:

     * `case["diagnosis_keywords"]` if present, else
     * `[case["expected_diagnosis"]]`.
   * If `_token_overlap_match` returns true, we treat it as a correct diagnosis:

     * `state["diagnosis_correct"] = True`
     * `log.diagnosis_correct = True`.

2. Detect treatment hits

   * Only after diagnosis is correct.
   * `treatment_keywords` from `treatment_keywords` / `expected_treatment_keywords`.
   * `_count_keyword_hits` returns how many such phrases appear in the last message.
   * This number is added to `state["treatment_hits"]` and `log.treatment_hits`.

3. Special case: “Diagnosis only” message

   * If you just gave a diagnosis (first time) and 0 treatment hits:

     * System responds with: “Okay doctor, I understand this could be X. What treatment or next steps do I need now?”
     * This pushes you towards a treatment plan before evaluation.

4. Heuristic “win” condition

   * If diagnosis is correct and `treatment_hits_total >= 2`:

     * `accepted_treatment = True`
     * `done = True`
     * Scores are filled:

       * `accuracy = 100`
       * `thoroughness = 90` if `turns <= 10` else `70`
       * `efficiency = 100 - (25 * hints_used) - 10 * max(0, turns - 6)` (clamped ≥ 0)
     * You get a closing message:

       * “COMMAND AI: Diagnosis and treatment protocols verified correct...”

### 7.2 LLM evaluator path

If the last doctor message is detected as a treatment attempt (`_is_treatment_attempt`), the state is passed to `agent_node` in `graph.py`:

1. Build a detailed evaluation prompt:

   * Includes:

     * True diagnosis
     * Treatment keywords
     * Hints used
     * Turns taken
     * Full transcript (doctor and patient)

2. Ask Gemini to return strict JSON:

   ```json
   {
     "accepted": true/false,
     "patient_reply": "...",
     "short_feedback": "...",
     "score_accuracy": 0-100,
     "score_thoroughness": 0-100,
     "score_efficiency": 0-100
   }
   ```

3. If parsing succeeds:

   * Append `patient_reply` as the next AI message.
   * If `accepted = true`:

     * `done = True`
     * `final_diagnosis = expected_diagnosis`
     * `final_feedback = short_feedback`
     * Scores set as returned.
     * Another closing line is appended:

       * “/// COMMAND AI: PROTOCOLS ACCEPTED. CASE CLOSED. ///”

4. If parsing fails:

   * Defaults to:

     * `accepted = False`
     * A generic “plan unclear” message.
   * The simulation continues.

### 7.3 Patient simulation branch

If not in evaluation mode:

* Compute `visible_symptoms = stages[: stage + 1]`.
* Construct a system prompt with:

  * Role, age, gender.
  * Chief complaint.
  * Current symptom data.
  * Behavior instructions (concise answers, no repeating “I don’t understand” forever, etc.).
* Ask Gemini for the next patient reply and append it.
* Increment `stage` until `max_stage`.

---

## 8. Hint system

Endpoint: `POST /api/hint`

* Request body: `{ "sessionId": "<uuid>" }` (frontend sends camelCase; backend normalizes).
* Backend behavior:

  * Uses case’s `hints` list.
  * Delivers hints in order:

    * First call → first hint, then increments `hints_used`.
    * Second call → second hint (or repeats last hint if you exceed list length), and so on.
  * Updates:

    * `log.hints_used`
    * `state["hints_used"]`

Frontend behavior:

* Displays a yellow hint box with:

  * `[INTEL RECEIVED] Hint X/Y: <hint text>`
* Per-level cap:

  * Internal state `hintsUsed`.
  * `maxRevealsPerLevel = 3`.
  * If `hintsUsed >= 3`, the “Reveal (hint)” button is disabled and message “NO STARS LEFT” is shown.

Scoring impact (as implemented):

* At summary:

  * If you used at least one hint:

    * Base stars are reduced by 1 (maximum 2 stars possible).
  * Hints also reduce efficiency in the evaluator scoring formula.

---

## 9. Reveal system (DX / TX reveal)

Endpoint: `POST /api/reveal-objective`

Request body:

```json
{
  "sessionId": "<uuid>",
  "objectiveId": "<optional>"
}
```

Behavior:

* If no hidden objectives left:

  * Returns message “No hidden objectives left.”
  * Leaves state unchanged.
* Otherwise:

  * Finds the first hidden objective (or later, a specific objective if `objectiveId` is used).
  * Marks:

    * `visible = True`
    * `achieved = True`
    * `revealed_by_user = True`
  * Increments:

    * `state["reveals_used"]`
    * `log.reveals_used`
  * Returns:

    * Updated objective list (public view).
    * `message = "Objective revealed at cost of 1 star."`
    * `reveals_used`

Scoring impact:

* In `/api/summary`, `reveals_used` reduces the stars for that level:

  * Base stars (0–3) are computed.
  * `final_stars = max(0, base_stars - reveals_used)`.

The design spec for reveals:

* Up to 3 reveals per level (DX/TX checkboxes).
* Each reveal costs 1 star from your total star pool and affects global rank (conceptually).
* If no stars are left in your global pool, reveals should not be allowed.

Implementation note:

* The backend currently applies the reveal penalty at the level’s star calculation.
* The global progress is computed as the sum of each level’s best stars.

---

## 10. Stars and scoring

Stars are calculated per mission (level) in `/api/summary`.

Inputs:

* `diagnosis_correct`
* `treatment_ok` (accepted treatment)
* `log.hints_used`
* `log.turns`
* `reveals_used`

Algorithm (current):

1. Diagnose / treatment correctness → base stars

   * If diagnosis is incorrect:

     * `base_stars = 0`
   * If diagnosis is correct but treatment is not accepted:

     * `base_stars = 1`
   * If diagnosis is correct and treatment accepted:

     * `base_stars = 3`
     * If `hints_used > 0`, `base_stars -= 1` (so max 2 stars)
     * If `turns > 12`, `base_stars -= 1` (long case penalty)
     * Clamp: `if base_stars < 1: base_stars = 1` for this scenario.

2. Apply reveal penalty

   * `final_stars = max(0, base_stars - reveals_used)`

3. Update `USER_PROGRESS`

   * Key: `"specialty|level"`
   * If `final_stars` > previous best, overwrite.

4. Numeric scores

   * Prefer `log.score_*` from the evaluator or heuristic.
   * Fallback defaults:

     * `accuracy = 100` if diagnosis correct else 30.
     * `thoroughness = 80` if no hints else 60.
     * `efficiency = 70`.

5. Feedback text

   * Builds an “After Action Report” string with:

     * Target diagnosis
     * Stage reached
     * Hints used
     * Reveals used
     * Turn count
   * Adds a tactical analysis paragraph based on how well you did.
   * Optionally appends `final_feedback` from the evaluator if present.

Stars are then used to drive the global rank system.

---

## 11. Rank system and campaign progress

Global stars are stored in `USER_PROGRESS` and summarized on the frontend.

Total values:

* `totalCompleted` = number of keys in `USER_PROGRESS` (levels played and recorded).
* `totalLevels` = 25 (assumed 5 per specialty × 5 specialties; adjust as needed).
* `totalStars` = sum of stars across all keys (max 75 = 25 levels × 3 stars).

Rank tiers:

* 0–9 stars: STUDENT
* 10–19 stars: INTERN
* 20–29 stars: RESIDENT
* 30–39 stars: FELLOW
* 40–49 stars: ATTENDING
* 50–59 stars: CHIEF
* 60–69 stars: LEGEND
* 70–75 stars: HIPPOCRATES

Example icons (for UI, badges, or emojis):

* STUDENT: 🎓
* INTERN: 🩺
* RESIDENT: 🧠
* FELLOW: 🧬
* ATTENDING: ⚕️
* CHIEF: ⭐
* LEGEND: 🏆
* HIPPOCRATES: 🏛️

Rank computation (`getRankInfo` in frontend):

* Pick the highest rank where `minStars <= totalStars`.
* Determine next rank’s floor (or global max 75 for Hippocrates).
* Compute progress within current rank band:

  ```js
  const currentFloor = current.minStars;
  const globalMaxStars = 75;
  const nextFloor = next ? next.minStars : globalMaxStars;

  let progressFraction;
  if (!next) {
    const spanToMax = Math.max(1, globalMaxStars - currentFloor);
    progressFraction = Math.min(1, (stars - currentFloor) / spanToMax);
  } else {
    const span = Math.max(1, nextFloor - currentFloor);
    progressFraction = Math.min(1, (stars - currentFloor) / span);
  }

  const progressPercent = Math.round(progressFraction * 100);
  ```

This drives the green XP bar shown in the header and campaign panel.

---

## 12. API reference

All endpoints are under `API_BASE`, for example `http://localhost:8000`.

### 12.1 Health

* GET `/api/health`
* Response example:

  ```json
  {
    "status": "operational",
    "system": "AG-C COMMAND"
  }
  ```

### 12.2 Specials and levels

* GET `/api/specialties`

  * Returns a list of strings, e.g. `["Neurology", "Cardiology"]`.

* GET `/api/levels?specialty=Neurology`

  * Returns a list of level numbers, e.g. `[1, 2, 3, 4, 5]`.

### 12.3 Start session

* POST `/api/start-session`

* Body:

  ```json
  {
    "specialty": "Neurology",
    "level": 1
  }
  ```

* Response (`StartSessionResponse`):

  ```json
  {
    "session_id": "...",
    "case_id": "...",
    "specialty": "Neurology",
    "level": 1,
    "difficulty": "easy",
    "patient_name": "Mr X",
    "chief_complaint": "Sudden onset weakness...",
    "max_stage": 4,
    "objectives": [
      {
        "id": "diagnosis",
        "label": "Ischemic stroke",
        "type": "diagnosis",
        "visible": false,
        "achieved": false,
        "revealed_by_user": false
      }
    ]
  }
  ```

### 12.4 Chat

* POST `/api/chat`

* Body:

  ```json
  {
    "sessionId": "<uuid>",
    "message": "I suspect this is an ischemic stroke..."
  }
  ```

* Backend normalizes `"sessionId"` → `"session_id"`.

* Response (`ChatResponse`):

  ```json
  {
    "reply": "Patient's response or closing message",
    "done": false,
    "stage": 2,
    "accepted_treatment": false,
    "hints_used": 1,
    "messages": [],
    "diagnosis_correct": true,
    "treatment_hits": 1,
    "objectives": [
      {
        "id": "diagnosis",
        "label": "Ischemic stroke",
        "type": "diagnosis",
        "visible": true,
        "achieved": true,
        "revealed_by_user": false
      }
    ]
  }
  ```

Notes:

* `messages` is empty because the frontend maintains the full chat; backend only returns the latest AI reply and status flags.
* `done` and `accepted_treatment` mark whether the case is finished.

### 12.5 Hint

* POST `/api/hint`
* Body: `{ "sessionId": "<uuid>" }`
* Response (`HintResponse`):

  ```json
  {
    "hint": "Check for sudden focal deficit and time of onset...",
    "hint_index": 1,
    "total_hints": 3
  }
  ```

### 12.6 Reveal objective

* POST `/api/reveal-objective`
* Body: `{ "sessionId": "<uuid>" }` or also `"objectiveId"` later.
* Response (`RevealObjectiveResponse`):

  ```json
  {
    "message": "Objective revealed at cost of 1 star.",
    "objectives": [ ...updated objectives without keywords... ],
    "reveals_used": 1
  }
  ```

### 12.7 Summary

* GET `/api/summary/<session_id>`
* Response (`SummaryResponse`):

  ```json
  {
    "session_id": "...",
    "case_id": "...",
    "specialty": "Neurology",
    "level": 1,
    "diagnosis": "ISCHEMIC STROKE",
    "feedback": "/// AFTER ACTION REPORT /// ...",
    "turns": 8,
    "accepted_treatment": true,
    "stage_when_accepted": 3,
    "hints_used": 1,
    "stars": 2,
    "score_accuracy": 100,
    "score_thoroughness": 90,
    "score_efficiency": 70,
    "diagnosis_correct": true,
    "treatment_ok": true,
    "reveals_used": 1
  }
  ```

### 12.8 Progress and reset

* GET `/api/progress`

  ```json
  {
    "progress": {
      "Neurology|1": 3,
      "Neurology|2": 1
    }
  }
  ```

* POST `/api/reset`

  * Clears all entries in `USER_PROGRESS`.
  * Returns:

    ```json
    {
      "status": "cleared",
      "progress": {}
    }
    ```

---

## 13. Frontend architecture

Main files from your snippet:

* `src/api.js`
* `src/App.css`
* `src/App.jsx` (main React component in the snippet)

### 13.1 api.js

* `handleResponse`
  Generic response handler that:

  * Reads `res.text()`.
  * Tries `JSON.parse`.
  * If `res.ok` is false, throws with `data.error` or status text.

* Exported helpers:

  * `getSpecialties()`: GET `/api/specialties`
  * `getLevels(specialty)`: GET `/api/levels?specialty=...`
  * `startSession({ specialty, level })`: POST `/api/start-session`
  * `sendChat({ sessionId, message })`: POST `/api/chat`
  * `requestHint({ sessionId })`: POST `/api/hint`
  * `getSummary(sessionId)`: GET `/api/summary/:sessionId`
  * `revealObjective({ sessionId, objectiveId })`: POST `/api/reveal-objective`

Note: `sessionId` camelCase in frontend; backend normalizes to `session_id`.

### 13.2 App layout and components

Top-level state:

* `step` = `"specialty" | "level" | "chat"`
* `specialties`, `levels`
* `selectedSpecialty`, `selectedLevel`
* `session` (from `startSession`)
* `messages` (chat log for UI)
* `input` (current text)
* `hint`, `summary`
* `progress` (from `/api/progress`)
* `hintsUsed` (per level)
* `theme` (`"dark"` or `"light"`)

Key components:

1. `App`

   * Handles routing through steps:

     * SpecialtyScreen → LevelScreen → ChatScreen.
   * Fetches specials and progress on mount.
   * Controls theme via `data-theme` on `<html>`.

2. `GameInfo`

   * Left panel card showing:

     * Current phase (select spec, level, or active).
     * Selected specialty and level, or current patient details.
     * Small summary of last operation if available.

3. `SpecialtyScreen`

   * Grid of specialties; each is a “card” button.
   * Clicking sets `selectedSpecialty` and moves to `step="level"`.

4. `LevelScreen`

   * Shows all levels for the chosen specialty.
   * Each level card:

     * Difficulty badge (BAS/STD/ADV) based on level.
     * Progress stars for that level using `progress["specialty|level"]`.
   * Clicking starts a new session.

5. `ChatScreen`

   * Chat HUD: messages, live indicator, hint / end mission buttons.

   * Shows a simple “objectives meta” row:

     * Reveals used this level: `hintsUsed / 3`
     * Stars left this level (for hint usage).

   * Chat window:

     * Renders `messages` with `MessageBubble`.
     * System messages (intro) are styled separately.

   * Input row:

     * Text input + “TRANSMIT” button (disabled when empty or loading).

   * Actions:

     * “REVEAL (HINT -1★)” button:

       * Calls `onHint` unless max reveals used or mission complete.
     * “END MISSION” button:

       * Calls `onSummary`.

   * Hint box:

     * Displays latest hint with an [INTEL RECEIVED] prefix.

6. `SummaryPanel`

   * Renders once `summary` is available.
   * Shows:

     * Overall rating (average of three scores).
     * StarRow for the level.
     * Bars for accuracy, intel/data, speed/efficiency.
     * Terminal-styled feedback text.

7. `StarRow`

   * Small UI utility to render three stars with filled/empty state.

8. Styling highlights (App.css)

   * Sci-fi, HUD-style UI:

     * Scanline overlay.
     * Neon cyan primary, indigo secondary.
     * Dark / light themes via CSS variables.
   * Rank display:

     * Shows current rank name.
     * Shows total stars and the requirement for next rank.
     * XP bar across current rank band.
   * Responsive layout:

     * Stacks panels vertically on narrow screens.

---

## 14. Running the project

Example local setup (adjust paths/commands for your environment).

### 14.1 Backend

Prerequisites:

* Python 3.10+
* A Google Gemini API key in environment variables

Steps:

```bash
cd backend

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt
# requirements.txt should include:
# flask, flask-cors, python-dotenv, langchain-core, langgraph,
# langchain-google-genai, pydantic
```

Set environment variables (example):

```bash
export GOOGLE_API_KEY="your-gemini-api-key"
export PORT=8000
```

Run:

```bash
python app.py
```

You should see logging like:

```text
Starting AG-C backend on port 8000
LangGraph workflow for PatientState compiled
```

### 14.2 Frontend

Prerequisites:

* Node.js (18+)
* npm or yarn

Steps:

```bash
cd frontend

npm install
```

Set `API_BASE` in `src/config.js`:

```js
export const API_BASE = "http://localhost:8000";
```

Run dev server:

```bash
npm run dev
```

Open the URL shown in the console (often `http://localhost:5173`).

---

## 15. Extending the project

Some natural next steps:

1. Wire DX/TX checkbox reveals to `/api/reveal-objective`

   * When user clicks a DX/TX reveal:

     * Call `revealObjective({ sessionId, objectiveId })`.
     * Update UI with returned objectives.
     * Decrement global star pool and enforce “no stars → no reveal” in the UI.

2. Persist sessions and progress in a database

   * Replace in-memory dicts with Redis or PostgreSQL.
   * Store:

     * user_id, session_id, case_id
     * messages, scores, stars
     * timestamped progress

3. Additional specialties and cases

   * Add more cases to `patient_cases.py`.
   * Ensure each has:

     * `expected_diagnosis`, `diagnosis_keywords`
     * `treatment_keywords`
     * `stages`
     * `hints`

4. Smarter treatment detection

   * Add custom synonyms and variations per case.
   * Allow partial credit for partial treatment phrases.

5. UX polish

   * Show objectives visually (checkboxes, icons) in the chat UI.
   * Add rank badges and icons next to the rank name.
   * Case selection filters by difficulty.

