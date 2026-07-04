import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


# ─── CONNEXION SUPABASE ────────────────────────────────────────────────────────
def get_supabase() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise ValueError("SUPABASE_URL et SUPABASE_KEY doivent être définis dans .env")

    return create_client(url, key)


supabase: Client = get_supabase()


# ─── FONCTIONS WORKFLOWS ───────────────────────────────────────────────────────

def save_workflow(workflow_id: str, user_id: str, request: str, status: str,
                  checkpoint_data: dict = {}, clarification_question: str = "",
                  fallback_context: dict = {}) -> dict:
    """Sauvegarde un nouveau workflow dans Supabase"""
    data = {
        "id": workflow_id,
        "user_id": user_id,
        "request": request,
        "status": status,
        "checkpoint_data": checkpoint_data,
        "clarification_question": clarification_question,
        "fallback_context": fallback_context
    }
    result = supabase.table("workflows").insert(data).execute()
    return result.data[0] if result.data else {}


def update_workflow_status(workflow_id: str, status: str,
                           checkpoint_data: dict = None,
                           clarification_question: str = None) -> dict:
    """Met à jour le statut d'un workflow"""
    data = {"status": status}
    if checkpoint_data is not None:
        data["checkpoint_data"] = checkpoint_data
    if clarification_question is not None:
        data["clarification_question"] = clarification_question

    result = supabase.table("workflows").update(data).eq("id", workflow_id).execute()
    return result.data[0] if result.data else {}


def get_workflow(workflow_id: str) -> dict:
    """Récupère un workflow depuis Supabase"""
    result = supabase.table("workflows").select("*").eq("id", workflow_id).execute()
    return result.data[0] if result.data else {}


def get_all_workflows(user_id: str) -> list:
    """Récupère tous les workflows d'un utilisateur"""
    result = supabase.table("workflows").select("*").eq("user_id", user_id).execute()
    return result.data if result.data else []


# ─── FONCTIONS LOGS ────────────────────────────────────────────────────────────

def save_logs(workflow_id: str, logs: list) -> None:
    """Sauvegarde les reasoning logs dans Supabase"""
    if not logs:
        return

    data = [
        {
            "workflow_id": workflow_id,
            "step": log["step"],
            "message": log["message"],
            "timestamp": log["timestamp"],
            "type": log["type"]
        }
        for log in logs
    ]
    supabase.table("reasoning_logs").insert(data).execute()


def get_logs(workflow_id: str) -> list:
    """Récupère tous les logs d'un workflow"""
    result = supabase.table("reasoning_logs")\
        .select("*")\
        .eq("workflow_id", workflow_id)\
        .order("step")\
        .execute()
    return result.data if result.data else []