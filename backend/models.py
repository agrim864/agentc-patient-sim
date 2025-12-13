# backend/models.py
from pydantic import BaseModel
from typing import Optional, List, Dict


class StartSessionRequest(BaseModel):
    specialty: Optional[str] = None
    level: Optional[int] = None
    difficulty: Optional[str] = None


class Objective(BaseModel):
    id: str
    label: str
    type: str  # "diagnosis" or "treatment"
    visible: bool
    achieved: bool
    revealed_by_user: bool = False


class StartSessionResponse(BaseModel):
    session_id: str
    case_id: str
    specialty: str
    level: int
    difficulty: str
    patient_name: str
    chief_complaint: str
    max_stage: int
    # New: case objectives (diagnosis + key treatments)
    objectives: List[Objective]


class ChatRequest(BaseModel):
    # We normalize sessionId/session_id in app.py before validation,
    # so here we just accept `session_id`.
    session_id: str
    message: str


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatResponse(BaseModel):
    reply: str
    done: bool
    stage: int
    accepted_treatment: bool
    hints_used: int
    messages: List[ChatMessage]

    # New: extra fields for UI/logic
    diagnosis_correct: bool = False
    treatment_hits: int = 0
    objectives: List[Objective] = []


class SummaryResponse(BaseModel):
    session_id: str
    case_id: str
    specialty: str
    level: int
    diagnosis: str
    feedback: str
    turns: int
    accepted_treatment: bool
    stage_when_accepted: int
    hints_used: int
    stars: int
    # Detailed Breakdown
    score_accuracy: int
    score_thoroughness: int
    score_efficiency: int
    # New: for more transparent UI
    diagnosis_correct: bool
    treatment_ok: bool
    reveals_used: int


class ProgressResponse(BaseModel):
    # key = "specialty|level", value = stars
    progress: Dict[str, int]


class HintRequest(BaseModel):
    session_id: str


class HintResponse(BaseModel):
    hint: str
    hint_index: int
    total_hints: int


class RevealObjectiveRequest(BaseModel):
    session_id: str
    # Optional – for now we always reveal the first hidden one,
    # but this keeps the API future-proof.
    objective_id: Optional[str] = None


class RevealObjectiveResponse(BaseModel):
    message: str
    objectives: List[Objective]
    reveals_used: int


class LogEntry(BaseModel):
    session_id: str
    case_id: str
    specialty: str
    level: int
    difficulty: str
    turns: int = 0
    accepted_treatment: bool = False
    stage_when_accepted: int = -1
    hints_used: int = 0
    stars: int = 0

    # Persist scores for metrics
    score_accuracy: int = 0
    score_thoroughness: int = 0
    score_efficiency: int = 0

    # New: store diagnosis / treatment progress and reveals
    diagnosis_correct: bool = False
    treatment_hits: int = 0
    reveals_used: int = 0
