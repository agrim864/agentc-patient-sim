# backend/graph.py

import json
import operator
import traceback
import logging
from typing import TypedDict, Annotated, List, Dict, Any

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# Logger for graph / LLM layer
logger = logging.getLogger("agentc_graph")

# Use 2.0 Flash as requested
gemini_llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0.3,  # Lower temp for more "tactical" precision
    max_tokens=None,
    max_retries=2,
)


class PatientState(TypedDict, total=False):
    messages: Annotated[List[BaseMessage], operator.add]
    case: Dict[str, Any]
    stage: int
    accepted_treatment: bool
    done: bool
    final_diagnosis: str
    final_feedback: str
    # New metrics passed from app.py logic to graph
    hints_used: int
    # Scores returned by LLM
    score_accuracy: int
    score_thoroughness: int
    score_efficiency: int


# ---------------- Helpers ----------------

def _format_conversation(messages: List[BaseMessage]) -> str:
    lines: List[str] = []
    for m in messages:
        if isinstance(m, HumanMessage):
            speaker = "DOCTOR (OPERATOR)"
        elif isinstance(m, AIMessage):
            speaker = "PATIENT (SUBJECT)"
        else:
            continue
        lines.append(f"{speaker}: {m.content}")
    return "\n".join(lines)


def _get_last_doctor_message(messages: List[BaseMessage]) -> str:
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return m.content
    return ""


def _is_treatment_attempt(text: str, case: Dict[str, Any]) -> bool:
    t = text.lower()
    keywords = [
        "diagnosis", "diagnose", "impression", "i suspect",
        "treatment", "plan", "prescribe", "recommend", "start you on",
    ]
    if any(k in t for k in keywords):
        return True
    for kw in case.get("expected_treatment_keywords", []):
        if kw.lower() in t:
            return True
    return False


def _cleanup_json(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        s = s.lstrip("`")
        if s.lower().startswith("json"):
            s = s[4:]
        if s.endswith("```"):
            s = s[:-3]
    return s.strip()


def _safe_llm_invoke(prompt: str, context: str) -> str:
    try:
        resp = gemini_llm.invoke([("human", prompt)])
        if hasattr(resp, "text") and resp.text:
            return resp.text
        if isinstance(resp.content, str):
            return resp.content
        return str(resp.content)
    except Exception as e:
        # Log error with context but not full prompt (to avoid logging conversation content)
        logger.error(
            "LLM error in context=%s: %r",
            context,
            e,
            exc_info=True,
        )
        traceback.print_exc()
        return ""


# ---------------- LangGraph node ----------------

def agent_node(state: PatientState) -> PatientState:
    new_state: PatientState = dict(state)
    messages: List[BaseMessage] = list(state.get("messages", []))
    case: Dict[str, Any] = dict(state.get("case", {}))
    hints_count = state.get("hints_used", 0)

    if not messages or not case:
        new_state["messages"] = messages
        return new_state

    last_doctor_text = _get_last_doctor_message(messages)
    stage = int(new_state.get("stage", 0))
    stages = case.get("stages", []) or []
    max_stage = max(len(stages) - 1, 0)

    # ---------- 1) Command AI Evaluator ----------
    if _is_treatment_attempt(last_doctor_text, case):
        conv_text = _format_conversation(
            [m for m in messages if isinstance(m, (HumanMessage, AIMessage))]
        )

        # Calculate current turn count
        turn_count = len([m for m in messages if isinstance(m, HumanMessage)])

        system_text = f"""
IDENTITY: Medical Oversight Command AI (MCO-AI).
MISSION: Evaluate Field Operator's diagnostic and treatment protocol accuracy.

CASE FILE:
- True Pathology: {case.get("expected_diagnosis", "")}
- Required Protocols (Keywords): {", ".join(case.get("expected_treatment_keywords", []))}
- Hints Used: {hints_count}
- Turns Taken: {turn_count}

SCORING ALGORITHM (0-100):
1. ACCURACY: Is the diagnosis correct and the treatment safe? (0=Wrong/Dangerous, 100=Standard of Care)
2. THOROUGHNESS: Did they ask relevant questions to rule out differentials? (0=Rushed/Guessing, 100=Comprehensive). If they spammed nonsense before solving, score this LOW (<50).
3. EFFICIENCY: Base 100. DEDUCT 25 pts per HINT. DEDUCT 10 pts per TURN over 6.

TASK:
1. Analyze the Operator's latest transmission.
2. Determine if the plan is acceptable.
3. Generate a simulated patient response.
4. Calculate the 3 scores.

OUTPUT FORMAT (Strict JSON):
{{
  "accepted": true/false,
  "patient_reply": "Natural patient response...",
  "short_feedback": "Tactical/Technical analysis...",
  "score_accuracy": 0-100,
  "score_thoroughness": 0-100,
  "score_efficiency": 0-100
}}
"""
        prompt = f"{system_text}\n\nTRANSCRIPT LOG:\n{conv_text}\n\nOUTPUT JSON:"

        raw_text = _safe_llm_invoke(prompt, context="evaluator")
        cleaned = _cleanup_json(raw_text)

        try:
            data = json.loads(cleaned)
        except Exception:
            logger.warning(
                "Failed to parse evaluator JSON; falling back. Raw length=%d",
                len(raw_text),
            )
            data = {
                "accepted": False,
                "patient_reply": "I'm not sure I understand that plan, Doctor. Can you explain?",
                "short_feedback": "PROTOCOL ERROR: Plan unclear or unparsed.",
                "score_accuracy": 0,
                "score_thoroughness": 0,
                "score_efficiency": 0,
            }

        accepted = bool(data.get("accepted", False))
        patient_reply = data.get("patient_reply", "").strip()
        short_feedback = data.get("short_feedback", "").strip()

        messages.append(AIMessage(content=patient_reply))
        new_state["messages"] = messages
        new_state["accepted_treatment"] = accepted

        if accepted:
            new_state["done"] = True
            new_state["final_diagnosis"] = case.get("expected_diagnosis", "")
            new_state["final_feedback"] = short_feedback
            # Save scores
            new_state["score_accuracy"] = int(data.get("score_accuracy", 70))
            new_state["score_thoroughness"] = int(data.get("score_thoroughness", 70))
            new_state["score_efficiency"] = int(data.get("score_efficiency", 70))

            logger.info(
                "Evaluator accepted plan: case_id=%s scores=(acc:%d,th:%d,eff:%d)",
                case.get("id", "unknown"),
                new_state["score_accuracy"],
                new_state["score_thoroughness"],
                new_state["score_efficiency"],
            )

            # Append a system message to close the loop in UI
            messages.append(
                AIMessage(content="/// COMMAND AI: PROTOCOLS ACCEPTED. CASE CLOSED. ///")
            )

        else:
            logger.info(
                "Evaluator rejected plan: case_id=%s (scores acc:%s th:%s eff:%s)",
                case.get("id", "unknown"),
                data.get("score_accuracy", "NA"),
                data.get("score_thoroughness", "NA"),
                data.get("score_efficiency", "NA"),
            )

        return new_state

    # ---------- 2) Patient Simulation Branch ----------
    stage = max(0, min(stage, max_stage))

    # Reveal symptoms based on current stage
    visible_symptoms = stages[: stage + 1]

    conv_text = _format_conversation(
        [m for m in messages if isinstance(m, (HumanMessage, AIMessage))]
    )

    symptom_data = (
        "\n".join(f"- {s}" for s in visible_symptoms) if visible_symptoms else "N/A"
    )

    system_text = f"""
SIMULATION MODE: ACTIVE.
ROLE: {case.get("name", "Subject")}, {case.get("age")}y/{case.get("gender")}.
COMPLAINT: {case.get("chief_complaint")}

CURRENT SYMPTOM DATA (Reveal ONLY this to the Doctor):
{symptom_data}

DIRECTIVES:
- You are a human patient. Do NOT mention you are an AI or simulation.
- React naturally to the Doctor's questions.
- If asked about symptoms NOT in your Current Data, say you haven't noticed that.
- Keep responses concise (1-3 sentences).
"""

    prompt = f"{system_text}\n\nTRANSCRIPT LOG:\n{conv_text}\n\nPATIENT RESPONSE:"
    patient_text = _safe_llm_invoke(prompt, context="patient").strip()

    if not patient_text:
        logger.warning("Empty patient_text from LLM; using fallback text")
        patient_text = "I'm feeling a bit overwhelmed, doctor."

    messages.append(AIMessage(content=patient_text))
    new_state["messages"] = messages

    # Progress stage if not maxed
    if stage < max_stage:
        new_state["stage"] = stage + 1
    else:
        new_state["stage"] = stage

    return new_state


def build_graph():
    workflow = StateGraph(PatientState)
    workflow.add_node("agent", agent_node)
    workflow.set_entry_point("agent")
    workflow.add_edge("agent", END)
    logger.info("LangGraph workflow for PatientState compiled")
    return workflow.compile()


graph_app = build_graph()
