import time
from fastapi import APIRouter, HTTPException
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
from app.agent.graph import run_workflow

router = APIRouter()

# Stockage temporaire des workflows en mémoire
# (sera remplacé par Supabase au J6)
workflows_store = {}


# ─── POST /api/workflow ─────────────────────────────────────────────────────────
@router.post("/workflow", response_model=WorkflowResponse)
async def create_workflow(body: WorkflowRequest):
    """
    Reçoit une demande utilisateur et lance la vraie agentic loop
    """
    try:
        # Lancer le workflow avec la vraie logique LangGraph + Qwen
        result = await run_workflow(
            user_id=body.user_id,
            request=body.request
        )

        # Sauvegarder le workflow en mémoire
        workflows_store[result["workflow_id"]] = result

        # Déterminer le next_step à afficher
        if result["status"] == "checkpoint_required":
            next_step = "Confirmation requise avant d'exécuter l'action"
        elif result["status"] == "executed":
            next_step = "Workflow terminé avec succès"
        else:
            next_step = "Workflow en cours..."

        return WorkflowResponse(
            workflow_id=result["workflow_id"],
            status=WorkflowStatus(result["status"]),
            next_step=next_step,
            checkpoint_data=result.get("checkpoint_data")
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── GET /api/workflow/{workflow_id} ───────────────────────────────────────────
@router.get("/workflow/{workflow_id}", response_model=WorkflowStateResponse)
async def get_workflow(workflow_id: str):
    """
    Retourne l'état complet d'un workflow
    """
    if workflow_id not in workflows_store:
        raise HTTPException(status_code=404, detail="Workflow introuvable")

    workflow = workflows_store[workflow_id]

    logs = [
        ReasoningLog(
            step=log["step"],
            message=log["message"],
            timestamp=log["timestamp"],
            type=LogType(log["type"])
        )
        for log in workflow.get("reasoning_logs", [])
    ]

    return WorkflowStateResponse(
        workflow_id=workflow_id,
        status=WorkflowStatus(workflow["status"]),
        logs=logs,
        result=workflow.get("checkpoint_data")
    )


# ─── POST /api/workflow/{workflow_id}/confirm ──────────────────────────────────
@router.post("/workflow/{workflow_id}/confirm", response_model=WorkflowResponse)
async def confirm_workflow(workflow_id: str, body: ConfirmRequest):
    """
    Confirme ou annule une action en attente de checkpoint
    """
    if workflow_id not in workflows_store:
        raise HTTPException(status_code=404, detail="Workflow introuvable")

    workflow = workflows_store[workflow_id]

    if body.confirmed:
        # Mettre à jour le statut
        workflow["status"] = "executed"
        workflows_store[workflow_id] = workflow

        return WorkflowResponse(
            workflow_id=workflow_id,
            status=WorkflowStatus.EXECUTED,
            next_step="Action confirmée et exécutée avec succès",
            checkpoint_data=None
        )
    else:
        workflow["status"] = "failed"
        workflows_store[workflow_id] = workflow

        return WorkflowResponse(
            workflow_id=workflow_id,
            status=WorkflowStatus.FAILED,
            next_step="Action annulée par l'utilisateur",
            checkpoint_data=None
        )


# ─── GET /api/workflow/{workflow_id}/logs ──────────────────────────────────────
@router.get("/workflow/{workflow_id}/logs", response_model=WorkflowLogsResponse)
async def get_workflow_logs(workflow_id: str):
    """
    Retourne tous les reasoning logs d'un workflow
    """
    if workflow_id not in workflows_store:
        raise HTTPException(status_code=404, detail="Workflow introuvable")

    workflow = workflows_store[workflow_id]

    logs = [
        ReasoningLog(
            step=log["step"],
            message=log["message"],
            timestamp=log["timestamp"],
            type=LogType(log["type"])
        )
        for log in workflow.get("reasoning_logs", [])
    ]

    return WorkflowLogsResponse(
        workflow_id=workflow_id,
        logs=logs
    )