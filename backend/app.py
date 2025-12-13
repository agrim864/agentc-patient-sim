# backend/app.py

import os
import uuid
import logging
from typing import Dict

from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from langchain_core.messages import HumanMessage, AIMessage

from graph import graph_app, PatientState
from patient_cases import pick_case, PATIENT_CASES
from models import (
    StartSessionRequest, StartSessionResponse, ChatRequest, ChatMessage,
    ChatResponse, SummaryResponse, HintRequest, HintResponse, LogEntry
)

# --------- LOGGING SETUP (MINIMAL, NON-SENSITIVE) ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("agentc_backend")

app = Flask(__name__)
CORS(app)

# --- GLOBAL STORES ---
# Key: "specialty|level", Value: int (stars)
USER_PROGRESS: Dict[str, int] = {}

SESSION_CASES: Dict[str, dict] = {}
SESSION_LOGS: Dict[str, LogEntry] = {}
SESSION_STATES: Dict[str, PatientState] = {}


# --- HELPERS ---

def _messages_to_dto(messages):
    dto = []
    for m in messages:
        if isinstance(m, HumanMessage):
            role = "user"
        elif isinstance(m, AIMessage):
            role = "assistant"
        else:
            role = "system"
        dto.append(ChatMessage(role=role, content=m.content))
    return dto

def _norm(text: str) -> str:
    return (text or "").lower().strip()

def _contains_any(text: str, keywords) -> bool:
    t = _norm(text)
    if not keywords:
        return False
    return any((kw or "").lower() in t for kw in keywords if kw)


# --- ROUTES ---

@app.errorhandler(Exception)
def handle_error(e):
    code = 500
    if isinstance(e, HTTPException):
        code = e.code
    # Log only type + message, not request body
    logger.exception("Unhandled exception occurred: %s", repr(e))
    return jsonify({"error": str(e)}), code


@app.route("/api/health", methods=["GET"])
def health():
    logger.debug("Health check ping")
    return jsonify({"status": "operational", "system": "AG-C COMMAND"})


@app.route("/api/specialties", methods=["GET"])
def specialties():
    unique = sorted({c["specialty"] for c in PATIENT_CASES})
    logger.info("Specialties requested; count=%d", len(unique))
    return jsonify(unique)


@app.route("/api/levels", methods=["GET"])
def levels():
    specialty = request.args.get("specialty")
    if not specialty:
        logger.warning("Levels requested without specialty parameter")
        return jsonify({"error": "SECTOR ID REQUIRED"}), 400

    levels = sorted({c["level"] for c in PATIENT_CASES if c["specialty"] == specialty})
    logger.info(
        "Levels requested for specialty=%s; levels_available=%s",
        specialty,
        levels,
    )
    return jsonify(levels)


@app.route("/api/progress", methods=["GET"])
def get_progress():
    """Returns the best star rating for each completed level."""
    logger.debug("Progress requested; entries=%d", len(USER_PROGRESS))
    return jsonify({"progress": USER_PROGRESS})


@app.route("/api/reset", methods=["POST"])
def reset_progress():
    """Wipes all user progress (Clear Data)."""
    USER_PROGRESS.clear()
    logger.info("User progress reset (all specialties/levels)")
    return jsonify({"status": "cleared", "progress": {}})


@app.route("/api/start-session", methods=["POST"])
def start_session():
    data = request.get_json(force=True, silent=True) or {}
    start_req = StartSessionRequest(**data)

    case = pick_case(
        specialty=start_req.specialty,
        level=start_req.level,
        difficulty=start_req.difficulty,
    )

    session_id = str(uuid.uuid4())
    SESSION_CASES[session_id] = case

    max_stage = len(case.get("stages", [])) - 1
    if max_stage < 0:
        max_stage = 0

    initial_state: PatientState = {
        "messages": [],
        "case": case,
        "stage": 0,
        "accepted_treatment": False,
        "done": False,
        "final_diagnosis": "",
        "final_feedback": "",
        "diagnosis_correct": False,
        "treatment_hits": 0,
        "score_accuracy": 0,
        "score_thoroughness": 0,
        "score_efficiency": 0,
        "hints_used": 0,
    }
    SESSION_STATES[session_id] = initial_state

    log = LogEntry(
        session_id=session_id,
        case_id=case["id"],
        specialty=case["specialty"],
        level=case["level"],
        difficulty=case["difficulty"],
        turns=0,
        accepted_treatment=False,
        stage_when_accepted=-1,
        hints_used=0,
        stars=0,
        score_accuracy=0,
        score_thoroughness=0,
        score_efficiency=0,
    )
    SESSION_LOGS[session_id] = log

    logger.info(
        "Session started: session_id=%s case_id=%s specialty=%s level=%d difficulty=%s",
        session_id,
        case["id"],
        case["specialty"],
        case["level"],
        case["difficulty"],
    )

    resp = StartSessionResponse(
        session_id=session_id,
        case_id=case["id"],
        specialty=case["specialty"],
        level=case["level"],
        difficulty=case["difficulty"],
        patient_name=case["name"],
        chief_complaint=case["chief_complaint"],
        max_stage=max_stage,
    )
    return jsonify(resp.model_dump())


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True, silent=True) or {}
    req = ChatRequest(**data)

    if req.session_id not in SESSION_CASES:
        logger.warning("Chat with invalid session_id=%s", req.session_id)
        return jsonify({"error": "INVALID SESSION ID"}), 400

    case = SESSION_CASES[req.session_id]
    prev_state = SESSION_STATES[req.session_id]
    log = SESSION_LOGS[req.session_id]

    log.turns += 1
    turn_number = log.turns

    messages = list(prev_state.get("messages", []))
    messages.append(HumanMessage(content=req.message))
    prev_state["messages"] = messages
    prev_state["hints_used"] = log.hints_used

    logger.info(
        "Chat turn: session_id=%s case_id=%s turn=%d",
        req.session_id,
        case["id"],
        turn_number,
    )

    # Already done?
    if prev_state.get("done"):
        closing = "/// MISSION STATUS: COMPLETE. Access 'End Mission' for debrief. ///"
        messages.append(AIMessage(content=closing))
        SESSION_STATES[req.session_id] = prev_state
        logger.info(
            "Chat received after completion: session_id=%s; returning closing message",
            req.session_id,
        )
        return jsonify(
            ChatResponse(
                reply=closing,
                done=True,
                stage=int(prev_state.get("stage", 0)),
                accepted_treatment=True,
                hints_used=log.hints_used,
                messages=[],
            ).model_dump()
        )

    # --- HEURISTIC FAST PATH ---
    text_norm = _norm(req.message)
    diag_keywords = case.get("diagnosis_keywords") or [case.get("expected_diagnosis", "")]
    diag_ok = bool(prev_state.get("diagnosis_correct", False))

    if not diag_ok and _contains_any(text_norm, diag_keywords):
        diag_ok = True
        prev_state["diagnosis_correct"] = True
        logger.info(
            "Diagnosis matched via heuristic: session_id=%s case_id=%s",
            req.session_id,
            case["id"],
        )

    treatment_keywords = case.get("treatment_keywords") or case.get(
        "expected_treatment_keywords", []
    )
    treatment_hits = int(prev_state.get("treatment_hits", 0))

    if diag_ok and treatment_keywords:
        msg_hits = 0
        for kw in treatment_keywords:
            if kw and kw.lower() in text_norm:
                msg_hits += 1
        treatment_hits += msg_hits
        prev_state["treatment_hits"] = treatment_hits

        if msg_hits > 0:
            logger.info(
                "Treatment keywords matched: session_id=%s case_id=%s msg_hits=%d total_hits=%d",
                req.session_id,
                case["id"],
                msg_hits,
                treatment_hits,
            )

    # Heuristic Win
    if diag_ok and treatment_hits >= 2:
        prev_state["accepted_treatment"] = True
        prev_state["done"] = True
        stage = int(prev_state.get("stage", 0))

        # --- SCORING ---
        log.score_accuracy = 100
        # Penalize if user flailed for too many turns
        log.score_thoroughness = 70 if log.turns > 10 else 90

        # Efficiency: Penalize Hints AND Turns
        hint_penalty = log.hints_used * 25
        turn_penalty = max(0, log.turns - 6) * 10
        log.score_efficiency = max(0, 100 - hint_penalty - turn_penalty)

        if log.stage_when_accepted == -1:
            log.stage_when_accepted = stage
        log.accepted_treatment = True
        SESSION_LOGS[req.session_id] = log

        logger.info(
            "Case solved via heuristic: session_id=%s case_id=%s turns=%d hints_used=%d scores=(acc:%d,th:%d,eff:%d)",
            req.session_id,
            case["id"],
            log.turns,
            log.hints_used,
            log.score_accuracy,
            log.score_thoroughness,
            log.score_efficiency,
        )

        closing = (
            "COMMAND AI: Diagnosis and treatment protocols verified correct. "
            "Patient outcome projected: OPTIMAL. "
            "Mission objectives met. Stand down and access Debrief."
        )
        messages.append(AIMessage(content=closing))
        SESSION_STATES[req.session_id] = prev_state

        return jsonify(
            ChatResponse(
                reply=closing,
                done=True,
                stage=stage,
                accepted_treatment=True,
                hints_used=log.hints_used,
                messages=[],
            ).model_dump()
        )

    # --- LANGGRAPH SLOW PATH ---
    result_state = graph_app.invoke(prev_state)
    SESSION_STATES[req.session_id] = result_state

    stage = int(result_state.get("stage", 0))
    accepted = bool(result_state.get("accepted_treatment", False))

    if accepted and not log.accepted_treatment:
        log.accepted_treatment = True
        log.stage_when_accepted = stage
        # Capture the specific scores generated by the LLM
        log.score_accuracy = result_state.get("score_accuracy", 70)
        log.score_thoroughness = result_state.get("score_thoroughness", 70)
        log.score_efficiency = result_state.get("score_efficiency", 70)
        logger.info(
            "Case solved via evaluator: session_id=%s case_id=%s stage=%d scores=(acc:%d,th:%d,eff:%d)",
            req.session_id,
            case["id"],
            stage,
            log.score_accuracy,
            log.score_thoroughness,
            log.score_efficiency,
        )
    elif log.accepted_treatment:
        accepted = True

    SESSION_LOGS[req.session_id] = log

    last_ai = ""
    for m in reversed(result_state.get("messages", [])):
        if isinstance(m, AIMessage):
            last_ai = m.content
            break

    return jsonify(
        ChatResponse(
            reply=last_ai or "Transmission received.",
            done=bool(result_state.get("done", False)),
            stage=stage,
            accepted_treatment=accepted,
            hints_used=log.hints_used,
            messages=[],
        ).model_dump()
    )


@app.route("/api/hint", methods=["POST"])
def hint():
    data = request.get_json(force=True, silent=True) or {}
    req = HintRequest(**data)

    if req.session_id not in SESSION_CASES:
        logger.warning("Hint requested for invalid session_id=%s", req.session_id)
        return jsonify({"error": "INVALID ID"}), 400

    case = SESSION_CASES[req.session_id]
    log = SESSION_LOGS[req.session_id]

    hints = case.get("hints", [])
    if not hints:
        logger.info(
            "Hint requested but no hints defined: session_id=%s case_id=%s",
            req.session_id,
            case["id"],
        )
        return jsonify(
            HintResponse(
                hint="INTEL EXHAUSTED.",
                hint_index=0,
                total_hints=0,
            ).model_dump()
        )

    idx = log.hints_used
    if idx >= len(hints):
        idx = len(hints) - 1

    hint_text = hints[idx]
    log.hints_used += 1
    SESSION_LOGS[req.session_id] = log

    logger.info(
        "Hint served: session_id=%s case_id=%s hint_index=%d/%d total_hints_used=%d",
        req.session_id,
        case["id"],
        idx + 1,
        len(hints),
        log.hints_used,
    )

    return jsonify(
        HintResponse(
            hint=hint_text,
            hint_index=idx + 1,
            total_hints=len(hints),
        ).model_dump()
    )


@app.route("/api/summary/<session_id>", methods=["GET"])
def summary(session_id: str):
    if session_id not in SESSION_CASES or session_id not in SESSION_STATES:
        logger.warning("Summary requested with unknown session_id=%s", session_id)
        return jsonify({"error": "Unknown session_id"}), 400

    case = SESSION_CASES[session_id]
    state = SESSION_STATES[session_id]
    log = SESSION_LOGS.get(session_id)

    stage = int(state.get("stage", 0))
    accepted = bool(state.get("accepted_treatment", log.accepted_treatment if log else False))

    if log and accepted and log.stage_when_accepted == -1:
        log.stage_when_accepted = stage

    hints_used = log.hints_used if log else 0
    stage_when_accepted = (
        log.stage_when_accepted if log and log.stage_when_accepted != -1 else stage
    )

    # --- SCORING LOGIC ---
    avg_score = (
        log.score_accuracy + log.score_thoroughness + log.score_efficiency
    ) / 3 if log else 0

    stars = 0
    if log and log.accepted_treatment:
        if avg_score >= 67:
            stars = 3
        elif avg_score >= 34:
            stars = 2
        else:
            stars = 1

    diagnosis = case.get("expected_diagnosis", "").upper()
    turns = log.turns if log else 0

    if log:
        log.accepted_treatment = accepted
        log.stars = stars
        SESSION_LOGS[session_id] = log

    # Update Global Progress
    key = f"{case['specialty']}|{case['level']}"
    current_best = USER_PROGRESS.get(key, 0)
    if stars > current_best:
        USER_PROGRESS[key] = stars

    logger.info(
        "Summary generated: session_id=%s case_id=%s stars=%d turns=%d hints=%d scores=(acc:%d,th:%d,eff:%d)",
        session_id,
        case["id"],
        stars,
        turns,
        hints_used,
        log.score_accuracy if log else 0,
        log.score_thoroughness if log else 0,
        log.score_efficiency if log else 0,
    )

    feedback = (
        f"/// AFTER ACTION REPORT ///\n"
        f"TARGET DIAGNOSIS: {diagnosis}\n"
        f"PERFORMANCE METRICS:\n"
        f"- SENSORY STAGE: {stage_when_accepted}\n"
        f"- INTEL REQUESTS: {hints_used}\n"
        f"- TRANSMISSION CYCLES: {turns}\n\n"
        f"TACTICAL ANALYSIS:\n"
        f"Operator correctly identified pathology and established containment protocols. "
        f"Efficiency rating calculated based on speed of diagnosis and reliance on external intel."
    )

    if state.get("final_feedback"):
        feedback += f"\n\nCOMMAND OVERSIGHT NOTE:\n{state.get('final_feedback')}"

    resp = SummaryResponse(
        session_id=session_id,
        case_id=case["id"],
        specialty=case["specialty"],
        level=case["level"],
        diagnosis=diagnosis,
        feedback=feedback,
        turns=turns,
        accepted_treatment=accepted,
        stage_when_accepted=stage_when_accepted,
        hints_used=hints_used,
        stars=stars,
        score_accuracy=log.score_accuracy if log else 0,
        score_thoroughness=log.score_thoroughness if log else 0,
        score_efficiency=log.score_efficiency if log else 0,
    )
    return jsonify(resp.model_dump())


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    logger.info("Starting AG-C backend on port %d", port)
    app.run(host="0.0.0.0", port=port)
