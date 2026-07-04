import os
import re
import time
import uuid
from typing import TypedDict
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.graph import StateGraph, END
from app.tools.definitions import TOOLS

load_dotenv()


# ─── ÉTAT DU GRAPH ─────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    messages: list
    workflow_id: str
    user_id: str
    reasoning_logs: list
    step_count: int
    status: str
    checkpoint_data: dict
    clarification_question: str
    fallback_context: dict
    ambiguity_checked: bool


# ─── FALLBACKS ─────────────────────────────────────────────────────────────────
FALLBACKS = {
    "send_email": {
        "question": "L'envoi de l'email a échoué. Que souhaitez-vous faire ?",
        "options": ["Réessayer avec une autre adresse", "Afficher le draft seulement", "Annuler"]
    },
    "schedule_meeting": {
        "question": "La planification de la réunion a échoué. Que souhaitez-vous faire ?",
        "options": ["Proposer un autre créneau", "Annuler la réunion"]
    },
    "generate_quote": {
        "question": "La génération du devis a échoué. Que souhaitez-vous faire ?",
        "options": ["Vérifier les données et réessayer", "Annuler"]
    }
}

# Tools sans check_for_ambiguity
TOOLS_WITHOUT_CHECK = [t for t in TOOLS if t.name != "check_for_ambiguity"]


# ─── FONCTIONS UTILITAIRES ─────────────────────────────────────────────────────

def detect_action(request: str) -> str:
    """Détecte l'action à exécuter selon la demande"""
    request_lower = request.lower()
    if any(w in request_lower for w in ["email", "mail", "envoie", "envoyer"]):
        return "send_email"
    if any(w in request_lower for w in ["réunion", "meeting", "rendez-vous", "rdv"]):
        return "schedule_meeting"
    if any(w in request_lower for w in ["devis", "facture", "prix", "quote"]):
        return "generate_quote"
    return "none"


def extract_email_args(request: str) -> dict:
    """Extrait les arguments pour send_email depuis la demande"""
    email_match = re.search(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}', request)
    recipient = email_match.group(0) if email_match else ""
    return {
        "recipient": recipient,
        "subject": "Message automatique",
        "body": request
    }


def extract_meeting_args(request: str) -> dict:
    """Extrait les arguments pour schedule_meeting depuis la demande"""
    return {
        "attendee": "Participant",
        "date": "demain",
        "time": "10:00",
        "duration": 60
    }


def extract_quote_args(request: str) -> dict:
    """Extrait les arguments pour generate_quote depuis la demande"""
    prices = re.findall(r'\d+(?:[.,]\d+)?', request)
    price = float(prices[0].replace(',', '.')) if prices else 100.0
    return {
        "customer_name": "Client",
        "items": ["Produit"],
        "prices": [price],
        "discount": 0.0
    }


# ─── NŒUDS DU GRAPH ────────────────────────────────────────────────────────────

def make_agent_node(llm_with_tools, llm_with_tools_no_check):
    def agent_node(state: AgentState) -> AgentState:
        step = state["step_count"] + 1

        log = {
            "step": step,
            "message": "Analyse de la demande en cours...",
            "timestamp": int(time.time() * 1000),
            "type": "info"
        }

        if state.get("ambiguity_checked"):
            response = llm_with_tools_no_check.invoke(state["messages"])
        else:
            response = llm_with_tools.invoke(state["messages"])

        if hasattr(response, "tool_calls") and response.tool_calls:
            tool_names = [tc["name"] for tc in response.tool_calls]
            decision_log = {
                "step": step,
                "message": f"Outils identifiés : {', '.join(tool_names)}",
                "timestamp": int(time.time() * 1000),
                "type": "info"
            }
        else:
            decision_log = {
                "step": step,
                "message": f"Réponse finale : {response.content[:100] if response.content else 'aucune'}",
                "timestamp": int(time.time() * 1000),
                "type": "info"
            }

        return {
            **state,
            "messages": state["messages"] + [response],
            "reasoning_logs": state["reasoning_logs"] + [log, decision_log],
            "step_count": step,
            "status": "running"
        }
    return agent_node


def tools_node(state: AgentState) -> AgentState:
    last_message = state["messages"][-1]
    step = state["step_count"] + 1
    new_logs = []
    new_messages = []
    fallback_triggered = None
    ambiguity_checked = state.get("ambiguity_checked", False)

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        new_logs.append({
            "step": step,
            "message": f"Exécution de '{tool_name}'...",
            "timestamp": int(time.time() * 1000),
            "type": "info"
        })

        tool_func = next((t for t in TOOLS if t.name == tool_name), None)

        if tool_func:
            try:
                result = tool_func.invoke(tool_args)

                new_logs.append({
                    "step": step,
                    "message": f"'{tool_name}' terminé avec succès",
                    "timestamp": int(time.time() * 1000),
                    "type": "info"
                })

                # Si check_for_ambiguity retourne is_ambiguous=False
                # → exécuter directement l'action dans le code
                if tool_name == "check_for_ambiguity":
                    ambiguity_checked = True
                    result_dict = result if isinstance(result, dict) else {}
                    is_ambiguous = result_dict.get("is_ambiguous", True)

                    if not is_ambiguous:
                        # Récupérer la demande originale
                        original_request = ""
                        for msg in state["messages"]:
                            if hasattr(msg, "content") and isinstance(msg.content, str):
                                original_request = msg.content
                                break

                        action = detect_action(original_request)
                        new_logs.append({
                            "step": step,
                            "message": f"Demande claire — exécution directe : {action}",
                            "timestamp": int(time.time() * 1000),
                            "type": "info"
                        })

                        # Choisir les args selon l'action
                        if action == "send_email":
                            args = extract_email_args(original_request)
                            action_tool = next(t for t in TOOLS if t.name == "send_email")
                        elif action == "schedule_meeting":
                            args = extract_meeting_args(original_request)
                            action_tool = next(t for t in TOOLS if t.name == "schedule_meeting")
                        elif action == "generate_quote":
                            args = extract_quote_args(original_request)
                            action_tool = next(t for t in TOOLS if t.name == "generate_quote")
                        else:
                            action_tool = None
                            args = {}

                        if action_tool:
                            try:
                                action_result = action_tool.invoke(args)
                                new_logs.append({
                                    "step": step + 1,
                                    "message": f"'{action}' exécuté avec succès",
                                    "timestamp": int(time.time() * 1000),
                                    "type": "info"
                                })
                                new_messages.append(
                                    ToolMessage(
                                        content=str(result),
                                        tool_call_id=tool_call["id"]
                                    )
                                )
                                return {
                                    **state,
                                    "messages": state["messages"] + new_messages,
                                    "reasoning_logs": state["reasoning_logs"] + new_logs,
                                    "step_count": step + 1,
                                    "ambiguity_checked": ambiguity_checked,
                                    "status": "checkpoint_required",
                                    "checkpoint_data": {
                                        "action": action,
                                        "args": args,
                                        "result": action_result,
                                        "message": f"Confirmer l'exécution de '{action}' ?"
                                    }
                                }

                            except ValueError as e:
                                error_msg = str(e)
                                new_logs.append({
                                    "step": step + 1,
                                    "message": f"Erreur dans '{action}' : {error_msg}",
                                    "timestamp": int(time.time() * 1000),
                                    "type": "error"
                                })
                                if action in FALLBACKS:
                                    fallback = FALLBACKS[action]
                                    fallback_triggered = {
                                        "tool_name": action,
                                        "error": error_msg,
                                        "question": fallback["question"],
                                        "options": fallback["options"]
                                    }
                                    new_logs.append({
                                        "step": step + 1,
                                        "message": f"Fallback déclenché : {fallback['question']}",
                                        "timestamp": int(time.time() * 1000),
                                        "type": "warning"
                                    })

                new_messages.append(
                    ToolMessage(
                        content=str(result),
                        tool_call_id=tool_call["id"]
                    )
                )

            except ValueError as e:
                error_msg = str(e)
                new_logs.append({
                    "step": step,
                    "message": f"Erreur dans '{tool_name}' : {error_msg}",
                    "timestamp": int(time.time() * 1000),
                    "type": "error"
                })
                if tool_name in FALLBACKS:
                    fallback = FALLBACKS[tool_name]
                    fallback_triggered = {
                        "tool_name": tool_name,
                        "error": error_msg,
                        "question": fallback["question"],
                        "options": fallback["options"]
                    }
                    new_logs.append({
                        "step": step,
                        "message": f"Fallback déclenché : {fallback['question']}",
                        "timestamp": int(time.time() * 1000),
                        "type": "warning"
                    })
                new_messages.append(
                    ToolMessage(
                        content=f"Erreur : {error_msg}",
                        tool_call_id=tool_call["id"]
                    )
                )

            except Exception as e:
                error_msg = str(e)
                new_logs.append({
                    "step": step,
                    "message": f"Erreur inattendue dans '{tool_name}' : {error_msg}",
                    "timestamp": int(time.time() * 1000),
                    "type": "error"
                })
                new_messages.append(
                    ToolMessage(
                        content=f"Erreur inattendue : {error_msg}",
                        tool_call_id=tool_call["id"]
                    )
                )

    new_state = {
        **state,
        "messages": state["messages"] + new_messages,
        "reasoning_logs": state["reasoning_logs"] + new_logs,
        "step_count": step,
        "ambiguity_checked": ambiguity_checked,
    }

    if fallback_triggered:
        new_state["status"] = "clarification_required"
        new_state["clarification_question"] = fallback_triggered["question"]
        new_state["fallback_context"] = fallback_triggered

    return new_state


def should_continue(state: AgentState) -> str:
    if state.get("status") == "clarification_required":
        return "end"

    if state.get("status") == "checkpoint_required":
        return "end"

    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        tool_names = [tc["name"] for tc in last_message.tool_calls]

        irreversible = ["send_email", "schedule_meeting"]
        if any(name in irreversible for name in tool_names):
            return "checkpoint"

        if "clarify_input" in tool_names:
            return "clarification"

        return "tools"

    return "end"


def checkpoint_node(state: AgentState) -> AgentState:
    last_message = state["messages"][-1]
    step = state["step_count"] + 1

    checkpoint_data = {
        "pending_tools": last_message.tool_calls,
        "message": "Confirmation requise avant d'exécuter cette action"
    }

    log = {
        "step": step,
        "message": "Confirmation requise avant d'exécuter l'action",
        "timestamp": int(time.time() * 1000),
        "type": "warning"
    }

    return {
        **state,
        "status": "checkpoint_required",
        "checkpoint_data": checkpoint_data,
        "reasoning_logs": state["reasoning_logs"] + [log],
        "step_count": step
    }


def clarification_node(state: AgentState) -> AgentState:
    last_message = state["messages"][-1]
    step = state["step_count"] + 1

    clarification_question = "Pouvez-vous préciser votre demande ?"
    for tool_call in last_message.tool_calls:
        if tool_call["name"] == "clarify_input":
            ambiguous = tool_call["args"].get("ambiguous_request", "")
            options = tool_call["args"].get("options", [])
            if options:
                clarification_question = f"{ambiguous} — Options : {', '.join(options)}"
            else:
                clarification_question = ambiguous

    log = {
        "step": step,
        "message": f"Question posée à l'utilisateur : {clarification_question}",
        "timestamp": int(time.time() * 1000),
        "type": "warning"
    }

    return {
        **state,
        "status": "clarification_required",
        "clarification_question": clarification_question,
        "reasoning_logs": state["reasoning_logs"] + [log],
        "step_count": step
    }


# ─── CONSTRUCTION DU GRAPH ─────────────────────────────────────────────────────

def build_graph(llm_with_tools, llm_with_tools_no_check):
    graph = StateGraph(AgentState)

    graph.add_node("agent", make_agent_node(llm_with_tools, llm_with_tools_no_check))
    graph.add_node("tools", tools_node)
    graph.add_node("checkpoint", checkpoint_node)
    graph.add_node("clarification", clarification_node)

    graph.set_entry_point("agent")

    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "checkpoint": "checkpoint",
            "clarification": "clarification",
            "end": END
        }
    )

    graph.add_conditional_edges(
        "tools",
        should_continue,
        {
            "tools": "tools",
            "checkpoint": "checkpoint",
            "clarification": "clarification",
            "end": END
        }
    )

    graph.add_edge("checkpoint", END)
    graph.add_edge("clarification", END)

    return graph.compile()


# ─── FONCTIONS PRINCIPALES ─────────────────────────────────────────────────────

def make_llm():
    return ChatOpenAI(
        model=os.getenv("QWEN_MODEL", "qwen-plus"),
        api_key=os.getenv("QWEN_API_KEY"),
        base_url=os.getenv("QWEN_BASE_URL"),
        temperature=0.1
    )


async def run_workflow(user_id: str, request: str) -> dict:
    llm = make_llm()
    llm_with_tools = llm.bind_tools(TOOLS)
    llm_with_tools_no_check = llm.bind_tools(TOOLS_WITHOUT_CHECK)

    workflow_id = str(uuid.uuid4())

    system_message = HumanMessage(content=f"""Tu es un agent d'automatisation de workflows professionnels.

Ton rôle : analyser et EXÉCUTER les demandes des utilisateurs.

PROCESSUS :
1. Appelle check_for_ambiguity pour analyser la demande
2. Si is_ambiguous=False → exécute l'action (send_email, generate_quote, schedule_meeting)
3. Si is_ambiguous=True → appelle clarify_input pour UNE question

Demande : {request}
""")

    initial_state: AgentState = {
        "messages": [system_message],
        "workflow_id": workflow_id,
        "user_id": user_id,
        "reasoning_logs": [],
        "step_count": 0,
        "status": "pending",
        "checkpoint_data": {},
        "clarification_question": "",
        "fallback_context": {},
        "ambiguity_checked": False
    }

    graph = build_graph(llm_with_tools, llm_with_tools_no_check)
    final_state = graph.invoke(initial_state)

    return {
        "workflow_id": workflow_id,
        "status": final_state["status"],
        "reasoning_logs": final_state["reasoning_logs"],
        "checkpoint_data": final_state.get("checkpoint_data", {}),
        "clarification_question": final_state.get("clarification_question", ""),
        "fallback_context": final_state.get("fallback_context", {}),
        "messages": final_state["messages"],
        "step_count": final_state["step_count"],
        "user_id": final_state["user_id"],
        "workflow_id": final_state["workflow_id"],
        "ambiguity_checked": final_state.get("ambiguity_checked", False)
    }


async def resume_workflow(workflow_id: str, answer: str, stored_state: dict) -> dict:
    llm = make_llm()
    llm_with_tools = llm.bind_tools(TOOLS)
    llm_with_tools_no_check = llm.bind_tools(TOOLS_WITHOUT_CHECK)

    messages = stored_state["messages"]
    messages.append(HumanMessage(content=f"Réponse : {answer}"))

    resumed_state: AgentState = {
        **stored_state,
        "messages": messages,
        "status": "running",
        "clarification_question": "",
        "fallback_context": {},
        "ambiguity_checked": False
    }

    graph = build_graph(llm_with_tools, llm_with_tools_no_check)
    final_state = graph.invoke(resumed_state)

    return {
        "workflow_id": workflow_id,
        "status": final_state["status"],
        "reasoning_logs": final_state["reasoning_logs"],
        "checkpoint_data": final_state.get("checkpoint_data", {}),
        "clarification_question": final_state.get("clarification_question", ""),
        "fallback_context": final_state.get("fallback_context", {}),
        "messages": final_state["messages"],
        "step_count": final_state["step_count"],
        "user_id": final_state["user_id"],
        "workflow_id": final_state["workflow_id"],
        "ambiguity_checked": final_state.get("ambiguity_checked", False)
    }