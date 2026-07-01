from pydantic import BaseModel
from typing import Optional, Any
from enum import Enum


# ─── STATUTS POSSIBLES D'UN WORKFLOW ───────────────────────────────────────────
class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    CLARIFICATION_REQUIRED = "clarification_required"  # nouveau
    CHECKPOINT_REQUIRED = "checkpoint_required"
    EXECUTED = "executed"
    FAILED = "failed"


# ─── TYPE DE LOG ───────────────────────────────────────────────────────────────
class LogType(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


# ─── REQUÊTES (ce que M4 envoie au backend) ────────────────────────────────────
class WorkflowRequest(BaseModel):
    user_id: str
    request: str


class ConfirmRequest(BaseModel):
    confirmed: bool


class ReplyRequest(BaseModel):
    answer: str  # la réponse de l'utilisateur à la question de clarification


# ─── RÉPONSES (ce que le backend renvoie à M4) ─────────────────────────────────
class WorkflowResponse(BaseModel):
    workflow_id: str
    status: WorkflowStatus
    next_step: Optional[str] = None
    checkpoint_data: Optional[Any] = None
    clarification_question: Optional[str] = None  # nouveau


class ReasoningLog(BaseModel):
    step: int
    message: str
    timestamp: int
    type: LogType


class WorkflowLogsResponse(BaseModel):
    workflow_id: str
    logs: list[ReasoningLog]


class WorkflowStateResponse(BaseModel):
    workflow_id: str
    status: WorkflowStatus
    logs: list[ReasoningLog]
    result: Optional[Any] = None
    clarification_question: Optional[str] = None  # nouveau