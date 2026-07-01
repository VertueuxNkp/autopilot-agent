from pydantic import BaseModel
from typing import Optional, Any
from enum import Enum


# STATUTS POSSIBLES D'UN WORKFLOW
class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    CHECKPOINT_REQUIRED = "checkpoint_required"
    EXECUTED = "executed"
    FAILED = "failed"


# TYPE DE LOG
class LogType(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


# REQUÊTES (ce que M4 envoie au backend)
class WorkflowRequest(BaseModel):
    user_id: str
    request: str


class ConfirmRequest(BaseModel):
    confirmed: bool  # True = confirmer, False = annuler


# RÉPONSES (ce que le backend renvoie à M4)
class WorkflowResponse(BaseModel):
    workflow_id: str
    status: WorkflowStatus
    next_step: Optional[str] = None
    checkpoint_data: Optional[Any] = None


class ReasoningLog(BaseModel):
    step: int
    message: str
    timestamp: int  # timestamp Unix en millisecondes
    type: LogType


class WorkflowLogsResponse(BaseModel):
    workflow_id: str
    logs: list[ReasoningLog]


class WorkflowStateResponse(BaseModel):
    workflow_id: str
    status: WorkflowStatus
    logs: list[ReasoningLog]
    result: Optional[Any] = None