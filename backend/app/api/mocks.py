from fastapi import APIRouter
from app.schemas import (
    WorkflowRequest,
    WorkflowResponse,
    WorkflowStatus,
    ConfirmRequest,
    WorkflowLogsResponse,
    WorkflowStateResponse,
    ReasoningLog,
    LogType,
)
import time

router = APIRouter()


# POST /api/workflow
# M4 appelle cet endpoint quand l'utilisateur soumet une demande
@router.post("/workflow", response_model=WorkflowResponse)
async def create_workflow(body: WorkflowRequest):
    """
    MOCK — sera remplacé par la vraie agentic loop J2-4
    Simule la création d'un workflow et retourne un ID fictif
    """
    return WorkflowResponse(
        workflow_id="mock-workflow-123",
        status=WorkflowStatus.RUNNING,
        next_step="Analyse de la demande en cours...",
        checkpoint_data=None
    )


# GET /api/workflow/{workflow_id}
# M4 appelle cet endpoint pour connaître l'état courant du workflow
@router.get("/workflow/{workflow_id}", response_model=WorkflowStateResponse)
async def get_workflow(workflow_id: str):
    """
    MOCK — sera remplacé par une vraie lecture Supabase J2-4
    Simule un workflow arrivé à un checkpoint
    """
    now = int(time.time() * 1000)  # timestamp en millisecondes

    return WorkflowStateResponse(
        workflow_id=workflow_id,
        status=WorkflowStatus.CHECKPOINT_REQUIRED,
        logs=[
            ReasoningLog(
                step=1,
                message="Vérification des ambiguïtés...",
                timestamp=now - 3000,
                type=LogType.INFO
            ),
            ReasoningLog(
                step=2,
                message="Ambiguïté détectée : prix unitaire manquant",
                timestamp=now - 2000,
                type=LogType.WARNING
            ),
            ReasoningLog(
                step=3,
                message="Question posée à l'utilisateur",
                timestamp=now - 1000,
                type=LogType.INFO
            ),
        ],
        result=None
    )


# POST /api/workflow/{workflow_id}/confirm
# M4 appelle cet endpoint quand l'utilisateur clique "Confirm" ou "Cancel"
@router.post("/workflow/{workflow_id}/confirm", response_model=WorkflowResponse)
async def confirm_workflow(workflow_id: str, body: ConfirmRequest):
    """
    MOCK — sera remplacé par la vraie logique de confirmation J4-5
    Simule une confirmation acceptée
    """
    if body.confirmed:
        return WorkflowResponse(
            workflow_id=workflow_id,
            status=WorkflowStatus.EXECUTED,
            next_step=None,
            checkpoint_data=None
        )
    else:
        return WorkflowResponse(
            workflow_id=workflow_id,
            status=WorkflowStatus.FAILED,
            next_step=None,
            checkpoint_data=None
        )


# GET /api/workflow/{workflow_id}/logs
# M4 appelle cet endpoint pour récupérer tous les reasoning logs d'un workflow
@router.get("/workflow/{workflow_id}/logs", response_model=WorkflowLogsResponse)
async def get_workflow_logs(workflow_id: str):
    """
    MOCK — sera remplacé par une vraie lecture Supabase J6-7
    Simule un historique complet de raisonnement
    """
    now = int(time.time() * 1000)

    return WorkflowLogsResponse(
        workflow_id=workflow_id,
        logs=[
            ReasoningLog(
                step=1,
                message="Vérification des ambiguïtés...",
                timestamp=now - 5000,
                type=LogType.INFO
            ),
            ReasoningLog(
                step=2,
                message="Ambiguïté détectée : prix unitaire manquant",
                timestamp=now - 4000,
                type=LogType.WARNING
            ),
            ReasoningLog(
                step=3,
                message="Question posée à l'utilisateur",
                timestamp=now - 3000,
                type=LogType.INFO
            ),
            ReasoningLog(
                step=4,
                message="Utilisateur a répondu : 200 euros",
                timestamp=now - 2000,
                type=LogType.INFO
            ),
            ReasoningLog(
                step=5,
                message="Outils identifiés : generate_quote, send_email",
                timestamp=now - 1000,
                type=LogType.INFO
            ),
        ]
    )