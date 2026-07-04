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
from app.database import (
    save_workflow,
    update_workflow_status,
    get_workflow,
    get_all_workflows,
    save_logs,
    get_logs
)

router = APIRouter()

# Stockage temporaire des messages en mémoire
# (les messages LangChain ne peuvent pas être sérialisés en JSON pour Supabase)
messages_store = {}


# ─── POST /api/workflow ─────────────────────────────────────────────────────────
@router.post("/workflow", response_model=WorkflowResponse)
async def create_workflow(body: WorkflowRequest):
    try:
        result = await run_workflow(
            user_id=body.user_id,
            request=body.request
        )

        workflow_id = result["workflow_id"]

        # Sauvegarder dans Supabase
        save_workflow(
            workflow_id=workflow_id,
            user_id=body.user_id,
            request=body.request,
            status=result["status"],
            checkpoint_data=result.get("checkpoint_data", {}),
            clarification_question=result.get("clarification_question", ""),
            fallback_context=result.get("fallback_context", {})
        )

        # Sauvegarder les logs dans Supabase
        save_logs(workflow_id, result.get("reasoning_logs", []))

        # Sauvegarder les messages en mémoire (pour resume_workflow)
        messages_store[workflow_id] = {
            "messages": result["messages"],
            "step_count": result["step_count"],
            "user_id": result["user_id"],
            "ambiguity_checked": result.get("ambiguity_checked", False)
        }

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


# ─── POST /api/workflow/{workflow_id}/reply ─────────────────────────────────────
@router.post("/workflow/{workflow_id}/reply", response_model=WorkflowResponse)
async def reply_workflow(workflow_id: str, body: ReplyRequest):
    """
    L'utilisateur répond à une question de clarification
    """
    # Vérifier dans Supabase
    workflow = get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow introuvable")

    if workflow["status"] != "clarification_required":
        raise HTTPException(
            status_code=400,
            detail="Ce workflow n'attend pas de clarification"
        )

    # Récupérer les messages depuis la mémoire
    if workflow_id not in messages_store:
        raise HTTPException(
            status_code=400,
            detail="Session expirée — veuillez relancer le workflow"
        )

    stored_messages = messages_store[workflow_id]

    try:
        result = await resume_workflow(
            workflow_id=workflow_id,
            answer=body.answer,
            stored_state={
                **stored_messages,
                "workflow_id": workflow_id,
                "reasoning_logs": [],
                "status": "running",
                "checkpoint_data": {},
                "clarification_question": "",
                "fallback_context": {}
            }
        )

        # Mettre à jour dans Supabase
        update_workflow_status(
            workflow_id=workflow_id,
            status=result["status"],
            checkpoint_data=result.get("checkpoint_data"),
            clarification_question=result.get("clarification_question")
        )

        # Sauvegarder les nouveaux logs
        save_logs(workflow_id, result.get("reasoning_logs", []))

        # Mettre à jour les messages en mémoire
        messages_store[workflow_id] = {
            "messages": result["messages"],
            "step_count": result["step_count"],
            "user_id": result["user_id"],
            "ambiguity_checked": result.get("ambiguity_checked", False)
        }

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
async def get_workflow_endpoint(workflow_id: str):
    """
    Retourne l'état complet d'un workflow depuis Supabase
    """
    workflow = get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow introuvable")

    # Récupérer les logs depuis Supabase
    raw_logs = get_logs(workflow_id)
    logs = [
        ReasoningLog(
            step=log["step"],
            message=log["message"],
            timestamp=log["timestamp"],
            type=LogType(log["type"])
        )
        for log in raw_logs
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
    """
    Confirme ou annule une action en attente de checkpoint
    """
    workflow = get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow introuvable")

    if body.confirmed:
        update_workflow_status(
            workflow_id=workflow_id,
            status="executed"
        )
        return WorkflowResponse(
            workflow_id=workflow_id,
            status=WorkflowStatus.EXECUTED,
            next_step="Action confirmée et exécutée avec succès",
            checkpoint_data=None
        )
    else:
        update_workflow_status(
            workflow_id=workflow_id,
            status="failed"
        )
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
    Retourne tous les reasoning logs depuis Supabase
    """
    workflow = get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow introuvable")

    raw_logs = get_logs(workflow_id)
    logs = [
        ReasoningLog(
            step=log["step"],
            message=log["message"],
            timestamp=log["timestamp"],
            type=LogType(log["type"])
        )
        for log in raw_logs
    ]

    return WorkflowLogsResponse(
        workflow_id=workflow_id,
        logs=logs
    )


# ─── GET /api/workflows/{user_id} ─────────────────────────────────────────────
@router.get("/workflows/{user_id}")
async def get_user_workflows(user_id: str):
    """
    Retourne tous les workflows d'un utilisateur
    """
    workflows = get_all_workflows(user_id)
    return {"user_id": user_id, "workflows": workflows}