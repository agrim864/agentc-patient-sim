# backend/app.py
import os
import uuid
import logging
import re
import difflib
from typing import Dict, List, Any



from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from langchain_core.messages import HumanMessage, AIMessage

from graph import graph_app, PatientState
from patient_cases import pick_case, PATIENT_CASES
from models import (
    StartSessionRequest,
    StartSessionResponse,
    ChatRequest,
    ChatMessage,
    ChatResponse,
    SummaryResponse,
    HintRequest,
    HintResponse,
    LogEntry,
    Objective,
    RevealObjectiveRequest,
    RevealObjectiveResponse,
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
# Key: "specialty|level", Value: int (best stars earned)
USER_PROGRESS: Dict[str, int] = {}

SESSION_CASES: Dict[str, dict] = {}
SESSION_LOGS: Dict[str, LogEntry] = {}
SESSION_STATES: Dict[str, PatientState] = {}


# --- TEXT HELPERS ---

def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", (text or "").lower()).strip()


def _contains_any(text: str, keywords: List[str]) -> bool:
    t = _normalize(text)
    if not keywords:
        return False
    return any(_normalize(kw) in t for kw in keywords if kw)





def _normalize_session_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """Support either sessionId or session_id coming from the frontend."""
    if "sessionId" in data and "session_id" not in data:
        data["session_id"] = data["sessionId"]
    return data


# --- OBJECTIVES HELPERS ---

def _build_objectives_for_case(case: dict) -> List[Dict[str, Any]]:
    """Build the hidden checklist: 1 diagnosis + key treatments."""
    objectives: List[Dict[str, Any]] = []

    expected_dx = (case.get("expected_diagnosis") or "").strip()
    if expected_dx:
        objectives.append({
            "id": "diagnosis",
            "label": expected_dx,
            "type": "diagnosis",
            "visible": False,
            "achieved": False,
            "revealed_by_user": False,
            "keywords": [expected_dx],
        })

    tx_keywords = case.get("treatment_keywords") or case.get(
        "expected_treatment_keywords", []
    )
    for idx, kw in enumerate(tx_keywords):
        label = (kw or "").strip()
        if not label:
            continue
        objectives.append({
            "id": f"treatment_{idx}",
            "label": label,
            "type": "treatment",
            "visible": False,
            "achieved": False,
            "revealed_by_user": False,
            "keywords": [label],
        })

    return objectives


def _fuzzy_token_match(a: str, b: str, threshold: float = 0.8) -> bool:
    """
    Return True if two tokens are 'close enough' to each other,
    e.g. minor spelling mistakes: 'pnemonia' ~ 'pneumonia'.
    """
    a = (a or "").strip()
    b = (b or "").strip()
    if not a or not b:
        return False
    return difflib.SequenceMatcher(None, a, b).ratio() >= threshold


def _phrase_hit(text: str, phrase: str, min_tokens: int = 1) -> bool:
    """
    Check if a phrase appears in the text, allowing for:
    - small spelling mistakes
    - token-level fuzzy matches

    We consider the phrase 'hit' if at least `min_tokens`
    of its tokens match some token in the text (exact or fuzzy).
    """
    t_tokens = _normalize(text).split()
    p_tokens = [tok for tok in _normalize(phrase).split() if tok]

    if not t_tokens or not p_tokens:
        return False

    hits = 0
    for p in p_tokens:
        for t in t_tokens:
            if t == p or _fuzzy_token_match(t, p):
                hits += 1
                break

    needed = min(len(p_tokens), max(1, min_tokens))
    return hits >= needed


def _token_overlap_match(
    text: str, target_phrases: List[str], min_overlap: int = 1
) -> bool:
    """
    Diagnosis helper: true if ANY target phrase 'matches' the text,
    where match = enough token overlap, allowing spelling mistakes.
    """
    for phrase in target_phrases or []:
        if not phrase:
            continue
        if _phrase_hit(text, phrase, min_tokens=min_overlap):
            return True
    return False


def _count_keyword_hits(text: str, keywords: List[str]) -> int:
    """
    Treatment helper: count how many treatment phrases appear in the text,
    allowing for minor spelling mistakes.
    """
    count = 0
    for kw in keywords or []:
        if not kw:
            continue
        if _phrase_hit(text, kw, min_tokens=1):
            count += 1
    return count


def _update_objectives_from_message(state: Dict[str, Any], msg: str) -> None:
    """
    Mark hidden objectives as achieved when the user 'basically' says them,
    even if they misspell a word or two.
    """
    objs = state.get("objectives") or []
    for obj in objs:
        if obj.get("achieved"):
            continue
        for kw in obj.get("keywords", []):
            if kw and _phrase_hit(msg, kw, min_tokens=1):
                obj["achieved"] = True
                obj["visible"] = True
                break
    state["objectives"] = objs



def _public_objectives(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Strip internal fields like 'keywords' before sending to frontend."""
    objs = state.get("objectives") or []
    clean: List[Dict[str, Any]] = []
    for obj in objs:
        clean.append({
            "id": obj.get("id"),
            "label": obj.get("label"),
            "type": obj.get("type"),
            "visible": bool(obj.get("visible", False)),
            "achieved": bool(obj.get("achieved", False)),
            "revealed_by_user": bool(obj.get("revealed_by_user", False)),
        })
    return clean


def _messages_to_dto(messages: List[Any]) -> List[ChatMessage]:
    dto: List[ChatMessage] = []
    for m in messages:
        if isinstance(m, HumanMessage):
            role = "user"
        elif isinstance(m, AIMessage):
            role = "assistant"
        else:
            role = "system"
        dto.append(ChatMessage(role=role, content=m.content))
    return dto


# --- ROUTES ---

@app.errorhandler(Exception)
def handle_error(e):
    code = 500
    if isinstance(e, HTTPException):
        code = e.code
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
    logger.debug("Progress requested; entries=%d", len(USER_PROGRESS))
    return jsonify({"progress": USER_PROGRESS})


@app.route("/api/reset", methods=["POST"])
def reset_progress():
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

    objectives = _build_objectives_for_case(case)

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
        "objectives": objectives,
        "reveals_used": 0,
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
        diagnosis_correct=False,
        treatment_hits=0,
        reveals_used=0,
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

    public_objs = _public_objectives(initial_state)

    resp = StartSessionResponse(
        session_id=session_id,
        case_id=case["id"],
        specialty=case["specialty"],
        level=case["level"],
        difficulty=case["difficulty"],
        patient_name=case["name"],
        chief_complaint=case["chief_complaint"],
        max_stage=max_stage,
        objectives=[Objective(**o) for o in public_objs],
    )
    return jsonify(resp.model_dump())


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True, silent=True) or {}
    data = _normalize_session_payload(data)
    req = ChatRequest(**data)

    if req.session_id not in SESSION_CASES:
        logger.warning("Chat with invalid session_id=%s", req.session_id)
        return jsonify({"error": "INVALID SESSION ID"}), 400

    case = SESSION_CASES[req.session_id]
    state = SESSION_STATES[req.session_id]
    log = SESSION_LOGS[req.session_id]

    log.turns += 1
    turn_number = log.turns

    messages = list(state.get("messages", []))
    messages.append(HumanMessage(content=req.message))
    state["messages"] = messages
    state["hints_used"] = log.hints_used

    logger.info(
        "Chat turn: session_id=%s case_id=%s turn=%d",
        req.session_id,
        case["id"],
        turn_number,
    )

    # Already done? Just echo a closing message.
    if state.get("done"):
        closing = "/// MISSION STATUS: COMPLETE. Access 'End Mission' for debrief. ///"
        messages.append(AIMessage(content=closing))
        SESSION_STATES[req.session_id] = state
        public_objs = _public_objectives(state)

        logger.info(
            "Chat received after completion: session_id=%s; returning closing message",
            req.session_id,
        )
        return jsonify(
            ChatResponse(
                reply=closing,
                done=True,
                stage=int(state.get("stage", 0)),
                accepted_treatment=True,
                hints_used=log.hints_used,
                messages=[],
                diagnosis_correct=bool(state.get("diagnosis_correct", False)),
                treatment_hits=int(state.get("treatment_hits", 0)),
                objectives=[Objective(**o) for o in public_objs],
            ).model_dump()
        )

    # --- HEURISTICS: Diagnosis / Treatment detection + objectives ---

    text = req.message or ""
    text_norm = _normalize(text)

    # Diagnosis detection
    diag_keywords = case.get("diagnosis_keywords") or [
        case.get("expected_diagnosis", "")
    ]
    diag_before = bool(state.get("diagnosis_correct", False))
    diag_after = diag_before

    if not diag_after and _token_overlap_match(text, diag_keywords, min_overlap=2):
        diag_after = True
        state["diagnosis_correct"] = True
        log.diagnosis_correct = True
        logger.info(
            "Diagnosis matched via heuristic: session_id=%s case_id=%s",
            req.session_id,
            case["id"],
        )

    # Treatment detection (only counts once we have some diagnosis)
    treatment_keywords = case.get("treatment_keywords") or case.get(
        "expected_treatment_keywords", []
    )
    treatment_hits_total = int(state.get("treatment_hits", 0))
    msg_hits = 0
    if diag_after and treatment_keywords:
        msg_hits = _count_keyword_hits(text, treatment_keywords)
        if msg_hits:
            treatment_hits_total += msg_hits
            state["treatment_hits"] = treatment_hits_total
            log.treatment_hits = treatment_hits_total
            logger.info(
                "Treatment keywords matched: session_id=%s case_id=%s msg_hits=%d total_hits=%d",
                req.session_id,
                case["id"],
                msg_hits,
                treatment_hits_total,
            )

    # Objectives update (unlock "words" the user has actually mentioned)
    _update_objectives_from_message(state, text)

    # --- Special case: user only gives diagnosis (no treatment yet) ---
    if not diag_before and diag_after and msg_hits == 0:
        # Just gave diagnosis for the first time; have patient ask about treatment.
        expected_dx = case.get("expected_diagnosis", "this condition")
        reply = (
            f"Okay doctor, I understand this could be {expected_dx}. "
            "What treatment or next steps do I need now?"
        )

        messages.append(AIMessage(content=reply))
        state["messages"] = messages
        SESSION_STATES[req.session_id] = state

        public_objs = _public_objectives(state)

        return jsonify(
            ChatResponse(
                reply=reply,
                done=False,
                stage=int(state.get("stage", 0)),
                accepted_treatment=False,
                hints_used=log.hints_used,
                messages=[],
                diagnosis_correct=diag_after,
                treatment_hits=treatment_hits_total,
                objectives=[Objective(**o) for o in public_objs],
            ).model_dump()
        )

    # --- Heuristic "win": diagnosis + enough treatment keywords ---
    if diag_after and treatment_hits_total >= 2:
        state["accepted_treatment"] = True
        state["done"] = True
        stage = int(state.get("stage", 0))

        # Scoring for heuristic win
        log.score_accuracy = 100
        log.score_thoroughness = 70 if log.turns > 10 else 90

        hint_penalty = log.hints_used * 25
        turn_penalty = max(0, log.turns - 6) * 10
        log.score_efficiency = max(0, 100 - hint_penalty - turn_penalty)

        if log.stage_when_accepted == -1:
            log.stage_when_accepted = stage
        log.accepted_treatment = True
        log.diagnosis_correct = True
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
        state["messages"] = messages
        SESSION_STATES[req.session_id] = state

        public_objs = _public_objectives(state)

        return jsonify(
            ChatResponse(
                reply=closing,
                done=True,
                stage=stage,
                accepted_treatment=True,
                hints_used=log.hints_used,
                messages=[],
                diagnosis_correct=True,
                treatment_hits=treatment_hits_total,
                objectives=[Objective(**o) for o in public_objs],
            ).model_dump()
        )

    # --- LANGGRAPH PATH ---
    result_state = graph_app.invoke(state)
    SESSION_STATES[req.session_id] = result_state

    stage = int(result_state.get("stage", 0))
    accepted = bool(result_state.get("accepted_treatment", False))

    if accepted and not log.accepted_treatment:
        log.accepted_treatment = True
        log.stage_when_accepted = stage
        log.score_accuracy = int(result_state.get("score_accuracy", 70))
        log.score_thoroughness = int(result_state.get("score_thoroughness", 70))
        log.score_efficiency = int(result_state.get("score_efficiency", 70))
        log.diagnosis_correct = True  # evaluator only accepts if dx is correct

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

    # Carry diagnosis/treatment flags forward into the state/log (if graph didn't overwrite)
    result_state["diagnosis_correct"] = bool(result_state.get("diagnosis_correct", diag_after))
    result_state["treatment_hits"] = int(result_state.get("treatment_hits", treatment_hits_total))
    log.diagnosis_correct = bool(result_state["diagnosis_correct"])
    log.treatment_hits = int(result_state["treatment_hits"])

    SESSION_LOGS[req.session_id] = log

    last_ai = ""
    for m in reversed(result_state.get("messages", [])):
        if isinstance(m, AIMessage):
            last_ai = m.content
            break

    public_objs = _public_objectives(result_state)

    return jsonify(
        ChatResponse(
            reply=last_ai or "Transmission received.",
            done=bool(result_state.get("done", False)),
            stage=stage,
            accepted_treatment=accepted,
            hints_used=log.hints_used,
            messages=[],
            diagnosis_correct=bool(result_state["diagnosis_correct"]),
            treatment_hits=int(result_state["treatment_hits"]),
            objectives=[Objective(**o) for o in public_objs],
        ).model_dump()
    )


@app.route("/api/hint", methods=["POST"])
def hint():
    data = request.get_json(force=True, silent=True) or {}
    data = _normalize_session_payload(data)
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

    # Keep state in sync for scoring / UI
    state = SESSION_STATES.get(req.session_id)
    if state is not None:
        state["hints_used"] = log.hints_used
        SESSION_STATES[req.session_id] = state

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


@app.route("/api/reveal-objective", methods=["POST"])
def reveal_objective():
    data = request.get_json(force=True, silent=True) or {}
    data = _normalize_session_payload(data)
    req = RevealObjectiveRequest(**data)

    session_id = req.session_id
    if session_id not in SESSION_STATES or session_id not in SESSION_CASES:
        logger.warning("Reveal requested for invalid session_id=%s", session_id)
        return jsonify({"error": "INVALID SESSION ID"}), 400

    state = SESSION_STATES[session_id]
    objs = state.get("objectives") or []

    target = None
    for obj in objs:
        if not obj.get("visible"):
            target = obj
            break

    if not target:
        logger.info(
            "Reveal requested but no hidden objectives left: session_id=%s",
            session_id,
        )
        public_objs = _public_objectives(state)
        resp = RevealObjectiveResponse(
            message="No hidden objectives left.",
            objectives=[Objective(**o) for o in public_objs],
            reveals_used=int(state.get("reveals_used", 0)),
        )
        return jsonify(resp.model_dump())

    target["visible"] = True
    target["achieved"] = True
    target["revealed_by_user"] = True

    reveals_used = int(state.get("reveals_used", 0)) + 1
    state["reveals_used"] = reveals_used
    state["objectives"] = objs
    SESSION_STATES[session_id] = state

    log = SESSION_LOGS.get(session_id)
    if log:
        log.reveals_used = reveals_used
        SESSION_LOGS[session_id] = log

    logger.info(
        "Objective revealed: session_id=%s objective_id=%s reveals_used=%d",
        session_id,
        target.get("id"),
        reveals_used,
    )

    public_objs = _public_objectives(state)
    resp = RevealObjectiveResponse(
        message="Objective revealed at cost of 1 star.",
        objectives=[Objective(**o) for o in public_objs],
        reveals_used=reveals_used,
    )
    return jsonify(resp.model_dump())


@app.route("/api/summary/<session_id>", methods=["GET"])
def summary(session_id: str):
    if session_id not in SESSION_CASES or session_id not in SESSION_STATES:
        logger.warning("Summary requested with unknown session_id=%s", session_id)
        return jsonify({"error": "Unknown session_id"}), 400

    case = SESSION_CASES[session_id]
    state = SESSION_STATES[session_id]
    log = SESSION_LOGS.get(session_id)

    stage = int(state.get("stage", 0))
    accepted = bool(
        state.get("accepted_treatment", log.accepted_treatment if log else False)
    )

    if log and accepted and log.stage_when_accepted == -1:
        log.stage_when_accepted = stage

    hints_used = log.hints_used if log else 0
    reveals_used = log.reveals_used if log else int(state.get("reveals_used", 0))
    stage_when_accepted = (
        log.stage_when_accepted if log and log.stage_when_accepted != -1 else stage
    )

    # --- Accuracy flags ---
    diagnosis_correct = bool(state.get("diagnosis_correct", False))
    treatment_ok = bool(
        state.get("accepted_treatment", False)
        or (log.accepted_treatment if log else False)
    )

    # --- Star scoring (based on correctness, hints, reveals, efficiency) ---
    if not diagnosis_correct:
        base_stars = 0
    elif diagnosis_correct and not treatment_ok:
        base_stars = 1
    else:
        base_stars = 3
        if hints_used > 0:
            base_stars -= 1
        if (log.turns if log else 0) > 12:
            base_stars -= 1
        if base_stars < 1:
            base_stars = 1

    final_stars = max(0, base_stars - reveals_used)

    # Scores: prefer LLM/evaluator scores if present, otherwise simple defaults
    score_accuracy = log.score_accuracy if log else (100 if diagnosis_correct else 30)
    score_thoroughness = (
        log.score_thoroughness if log else (80 if hints_used == 0 else 60)
    )
    score_efficiency = log.score_efficiency if log else 70

    turns = log.turns if log else 0
    diagnosis = (case.get("expected_diagnosis", "") or "").upper()

    if log:
        log.accepted_treatment = treatment_ok
        log.stars = final_stars
        log.score_accuracy = score_accuracy
        log.score_thoroughness = score_thoroughness
        log.score_efficiency = score_efficiency
        log.diagnosis_correct = diagnosis_correct
        log.reveals_used = reveals_used
        SESSION_LOGS[session_id] = log

    # Update global progress
    key = f"{case['specialty']}|{case['level']}"
    current_best = USER_PROGRESS.get(key, 0)
    if final_stars > current_best:
        USER_PROGRESS[key] = final_stars

    # Honest AFTER ACTION REPORT text
    if not diagnosis_correct:
        analysis = (
            "Operator did not reach the correct diagnosis. Further drills on symptom "
            "patterns and stroke mimics are recommended before advancing difficulty."
        )
    elif diagnosis_correct and not treatment_ok:
        analysis = (
            "Operator correctly identified the underlying pathology but did not outline "
            "a complete acute treatment and secondary prevention plan."
        )
    else:
        analysis = (
            "Operator correctly identified the pathology and proposed an appropriate "
            "treatment plan. Efficiency is based on number of turns and reliance on hints."
        )

    feedback = (
        "/// AFTER ACTION REPORT ///\n"
        f"TARGET DIAGNOSIS: {diagnosis}\n"
        "PERFORMANCE METRICS:\n"
        f"- SENSORY STAGE: {stage_when_accepted}\n"
        f"- INTEL REQUESTS (HINTS): {hints_used}\n"
        f"- OBJECTIVES REVEALED: {reveals_used}\n"
        f"- TRANSMISSION CYCLES: {turns}\n\n"
        "TACTICAL ANALYSIS:\n"
        f"{analysis}"
    )

    if state.get("final_feedback"):
        feedback += f"\n\nCOMMAND OVERSIGHT NOTE:\n{state.get('final_feedback')}"

    logger.info(
        "Summary generated: session_id=%s case_id=%s stars=%d turns=%d hints=%d reveals=%d scores=(acc:%d,th:%d,eff:%d)",
        session_id,
        case["id"],
        final_stars,
        turns,
        hints_used,
        reveals_used,
        score_accuracy,
        score_thoroughness,
        score_efficiency,
    )

    resp = SummaryResponse(
        session_id=session_id,
        case_id=case["id"],
        specialty=case["specialty"],
        level=case["level"],
        diagnosis=diagnosis,
        feedback=feedback,
        turns=turns,
        accepted_treatment=treatment_ok,
        stage_when_accepted=stage_when_accepted,
        hints_used=hints_used,
        stars=final_stars,
        score_accuracy=score_accuracy,
        score_thoroughness=score_thoroughness,
        score_efficiency=score_efficiency,
        diagnosis_correct=diagnosis_correct,
        treatment_ok=treatment_ok,
        reveals_used=reveals_used,
    )
    return jsonify(resp.model_dump())


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    logger.info("Starting AG-C backend on port %d", port)
    app.run(host="0.0.0.0", port=port)
