# backend/models.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict

class StartSessionRequest(BaseModel):
    specialty: Optional[str] = None 
    level: Optional[int] = None
    difficulty: Optional[str] = None

class StartSessionResponse(BaseModel):
    session_id: str
    case_id: str
    specialty: str
    level: int
    difficulty: str
    patient_name: str
    chief_complaint: str
    max_stage: int

class ChatRequest(BaseModel):
    # accept "sessionId" from JSON and map to session_id
    session_id: str = Field(alias="sessionId")
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
    # NEW: Detailed Breakdown
    score_accuracy: int
    score_thoroughness: int
    score_efficiency: int

class ProgressResponse(BaseModel):
    # key = "specialty|level", value = stars
    progress: Dict[str, int]

class HintRequest(BaseModel):
    # same idea here
    session_id: str = Field(alias="sessionId")

class HintResponse(BaseModel):
    hint: str
    hint_index: int
    total_hints: int

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
    # NEW: Persist scores for metrics
    score_accuracy: int = 0
    score_thoroughness: int = 0
    score_efficiency: int = 0

class Config:
    allow_population_by_field_name = True
    allow_population_by_alias = True