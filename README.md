# AGENT-C (Agentic Clinic)

AGENT-C is a gamified clinical reasoning simulator. You play as the “Doctor / Operator” over a radio-style chat interface: ask questions, form a diagnosis, propose treatment, and then debrief with a scored After Action Report. 

This is a training-style simulation only. It is not medical advice.

## Tech stack

Backend

* Python + Flask 
* LangGraph for the conversation flow (patient simulation + evaluator) 
* Gemini via LangChain (langchain_google_genai) 

Frontend

* React + Vite
* Single-page flow: Boot -> Specialty -> Level -> Chat -> Summary 

## Key gameplay features (including the missing ones)

Mission Debrief (short “review” after each level)

* When you end a mission, you get a compact “MISSION DEBRIEF” card with:

  * Overall rating = average of Accuracy + Intel/Data + Speed/Eff
  * Stars earned for that mission
  * Counts for hints used and objectives revealed
  * The After Action Report text 

Rank system (campaign-wide)

* Your rank is based on total stars earned across all missions:

  * 0–9★ STUDENT
  * 10–19★ INTERN
  * 20–29★ RESIDENT
  * 30–39★ FELLOW
  * 40–49★ ATTENDING
  * 50–59★ CHIEF
  * 60–69★ LEGEND
  * 70+★ HIPPOCRATES 

Objectives that “light up” as you discover them

* Objectives can be hidden and show as “????” until they’re revealed. 
* Objectives update during play as you mention relevant concepts (diagnosis and treatment items). 

Support tools with real tradeoffs

* Intel Hint: gives you a hint, but can reduce stars/efficiency scoring. 
* Reveal Objective (-1★): reveals a hidden objective, but costs one star each time (UI caps reveals at 3 per level). turn86file3L34-L36

Progress saving + restore code (portable campaign save)

* Best stars per mission are stored locally in the browser. 
* You can export/import progress via a single numeric restore code (base-4 packed into a BigInt). 

## Project structure (logical)

Backend

* app.py

  * Flask routes (/health, /specialties, /levels, /start-session, /chat, /hint, /reveal-objective, /summary) file14L21-L55
  * Session stores (in-memory)
  * Fast heuristics for early “case closed”
  * Objectives build + objective updates
  * Final summary / star scoring / After Action Report turn86file8L36-L55
* graph.py

  * LangGraph flow node that runs either:

    * Evaluator (treatment-plan check + strict JSON scores)
    * Patient simulation (stage-limited symptom reveal)
* models.py

  * Pydantic request/response models
* patient_cases.py

  * Case bank (specialty/level/difficulty, stages, keywords, hints)

Frontend

* App.jsx

  * Boot screen + backend connection check 
  * Campaign UI (mission map + rank)
  * Chat UI (send, hint, reveal, end mission) 
  * Local progress + restore code (export/import) 
* api.js

  * Backend fetch helpers
* config.js

  * API base URL configuration
* App.css

  * Styling

## Core gameplay loop

1. Boot

* Frontend checks backend reachability and shows ONLINE/OFFLINE status, plus the API base being used. L54-L58

2. Choose Specialty -> Level

* Each level maps to a specific patient case selected on the backend. 

3. Chat (radio-style)

* Ask focused questions (history, symptoms, red flags).
* The case is staged: only symptom data up to the current stage is “visible” to the patient simulator. 

4. Optional support tools

* Intel Hint
* Reveal Objective (-1★)

5. End Mission -> Debrief

* Shows overall rating, stars, 3 score bars, and the After Action Report text. 

6. Campaign progression (local)

* Best stars per mission saved locally; can be exported/imported via restore code. -L58

## Where and how the LLM is used

AGENT-C uses the LLM in two places inside the LangGraph flow:

1. Evaluator branch (LLM-driven “Command AI” check)

* Triggered when the system treats your message as a treatment-plan attempt.
* The model must output strict JSON:

  * accepted (true/false)
  * patient_reply
  * short_feedback
  * score_accuracy / score_thoroughness / score_efficiency 
* If accepted, the graph marks the case done, stores final_feedback + scores, and adds a “CASE CLOSED” message. 
* If parsing fails, it falls back to a safe “not accepted” response. 

2. Patient simulation branch (LLM-driven patient)

* The model role-plays the patient and is instructed to reveal only the currently visible symptom data (stages up to current stage). 
* If asked about symptoms not in current data, it should say they haven’t noticed that. 

Backend also runs a fast heuristic path before calling LangGraph:

* If diagnosis + enough treatment keyword hits are detected, the backend can close the case immediately without the evaluator. 
* Otherwise it calls `graph_app.invoke(state)` and uses the LLM-driven result. 

## Scoring and stars (how it works)

Stars (0–3) in /api/summary

* Base:

  * 0 stars: diagnosis not correct
  * 1 star: diagnosis correct but treatment not accepted
  * 3 stars: diagnosis correct and treatment accepted 
* Penalties (only if base is 3):

  * If any hints used: -1
  * If turns > 12: -1
  * Minimum becomes 1 (before reveal spend) 
* Reveal spend:

  * final_stars = max(0, base_stars - reveals_used) 

Detailed scores (0–100)

* If the evaluator accepted your plan, it provides the 3 scores (accuracy, thoroughness, efficiency). 
* Summary prefers those evaluator scores when present. 

After Action Report text

* Summary returns a structured “/// AFTER ACTION REPORT ///” plus an extra “COMMAND OVERSIGHT NOTE” if the evaluator wrote final_feedback. 

## API (current)

Health

* GET /api/health 

Campaign map

* GET /api/specialties 
* GET /api/levels?specialty=... 

Session

* POST /api/start-session

  * Body: specialty (string), level (int), difficulty (optional)
  * Returns session_id + case metadata + objectives 

Chat

* POST /api/chat

  * Body: session_id (or sessionId) + message
  * Returns: reply, done, stage, accepted_treatment, hints_used, diagnosis_correct, objectives, etc.

Hints

* POST /api/hint

Reveal objective

* POST /api/reveal-objective

  * Reveals an objective at cost of 1 star (counted in reveals_used). 

Summary / Debrief

* GET /api/summary/<session_id> 

## Frontend behavior (important)

Boot screen

* Shows connect/load steps and the backend API base. 
* If offline, shows a retry button. 

In-mission actions

* INTEL HINT, REVEAL OBJ (-1★), END MISSION. 
* Reveals are capped at 3 per level in the UI. 

Mission Debrief display

* Overall rating + stars + 3 score bars + after action report text. 

Campaign save / restore

* localStorage key: agentc_progress_v1 
* Restore code is base-4 packed into one numeric string. 

Rank tiers

* Implemented directly in App.jsx (see tier thresholds above). 

## Configuration

Backend environment

* GOOGLE_API_KEY (required for Gemini calls)

Frontend environment

* VITE_API_BASE

  * If set, it is used as the API base.

## Run locally

Backend

1. Create + activate a virtual environment
2. Install deps
3. Set GOOGLE_API_KEY
4. Run Flask (example)

   * python app.py

Frontend

1. npm install
2. npm run dev
3. Open the Vite URL (usually [http://localhost:5173](http://localhost:5173))

## Notes / limitations

* No database: sessions are in-memory; active sessions disappear on backend restart.
* Campaign progress is local (browser storage). Backend does not store campaign progress in this build.
* LLM behavior can vary; evaluator is constrained to strict JSON but can still fail and fall back. 
* This is a training simulation, not clinical guidance.
