import time
from fastapi import APIRouter, HTTPException
from app.schemas import (
    WorkflowRequest,
    WorkflowResponse,
    WorkflowStatus,
    ConfirmRequest,
    ReplyRequest,
    WorkflowLogsResponse,
    WorkflowStateResponse,
    ReasoningLog,
    LogType,
)
from app.agent.graph import run_workflow, resume_workflow

router = APIRouter()

# Stockage temporaire en mémoire (remplacé par Supabase au J6)
workflows_store = {}


# ─── POST /api/workflow ─────────────────────────────────────────────────────────
@router.post("/workflow", response_model=WorkflowResponse)
async def create_workflow(body: WorkflowRequest):
    try:
        result = await run_workflow(
            user_id=body.user_id,
            request=body.request
        )

        # Sauvegarder l'état complet du workflow
        workflows_store[result["workflow_id"]] = result

        # Déterminer le next_step
        if result["status"] == "clarification_required":
            next_step = result.get("clarification_question", "Précision requise")
        elif result["status"] == "checkpoint_required":
            next_step = "Confirmation requise avant d'exécuter l'action"
        elif result["status"] == "executed":
            next_step = "Workflow terminé avec succès"
        else:
            next_step = "Workflow en cours..."

        return WorkflowResponse(
            workflow_id=result["workflow_id"],
            status=WorkflowStatus(result["status"]),
            next_step=next_step,
            checkpoint_data=result.get("checkpoint_data"),
            clarification_question=result.get("clarification_question")
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── POST /api/workflow/{workflow_id}/reply ─────────────────────────────────────
@router.post("/workflow/{workflow_id}/reply", response_model=WorkflowResponse)
async def reply_workflow(workflow_id: str, body: ReplyRequest):
    """
    L'utilisateur répond à une question de clarification
    Le workflow reprend avec cette réponse
    """
    if workflow_id not in workflows_store:
        raise HTTPException(status_code=404, detail="Workflow introuvable")

    workflow = workflows_store[workflow_id]

    if workflow["status"] != "clarification_required":
        raise HTTPException(
            status_code=400,
            detail="Ce workflow n'attend pas de clarification"
        )

    try:
        result = await resume_workflow(
            workflow_id=workflow_id,
            answer=body.answer,
            stored_state=workflow
        )

        # Mettre à jour l'état sauvegardé
        workflows_store[workflow_id] = result

        # Déterminer le next_step
        if result["status"] == "clarification_required":
            next_step = result.get("clarification_question", "Précision requise")
        elif result["status"] == "checkpoint_required":
            next_step = "Confirmation requise avant d'exécuter l'action"
        elif result["status"] == "executed":
            next_step = "Workflow terminé avec succès"
        else:
            next_step = "Workflow en cours..."

        return WorkflowResponse(
            workflow_id=workflow_id,
            status=WorkflowStatus(result["status"]),
            next_step=next_step,
            checkpoint_data=result.get("checkpoint_data"),
            clarification_question=result.get("clarification_question")
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── GET /api/workflow/{workflow_id} ───────────────────────────────────────────
@router.get("/workflow/{workflow_id}", response_model=WorkflowStateResponse)
async def get_workflow(workflow_id: str):
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
        result=workflow.get("checkpoint_data"),
        clarification_question=workflow.get("clarification_question")
    )


# ─── POST /api/workflow/{workflow_id}/confirm ──────────────────────────────────
@router.post("/workflow/{workflow_id}/confirm", response_model=WorkflowResponse)
async def confirm_workflow(workflow_id: str, body: ConfirmRequest):
    if workflow_id not in workflows_store:
        raise HTTPException(status_code=404, detail="Workflow introuvable")

    workflow = workflows_store[workflow_id]

    if body.confirmed:
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