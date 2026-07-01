import os
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


# ─── NŒUDS DU GRAPH ────────────────────────────────────────────────────────────

def make_agent_node(llm_with_tools):
    def agent_node(state: AgentState) -> AgentState:
        step = state["step_count"] + 1

        log = {
            "step": step,
            "message": "Analyse de la demande en cours...",
            "timestamp": int(time.time() * 1000),
            "type": "info"
        }

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
                "message": "Réponse directe générée sans outil",
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
                new_messages.append(
                    ToolMessage(
                        content=str(result),
                        tool_call_id=tool_call["id"]
                    )
                )
            except Exception as e:
                new_logs.append({
                    "step": step,
                    "message": f"Erreur dans '{tool_name}' : {str(e)}",
                    "timestamp": int(time.time() * 1000),
                    "type": "error"
                })
                new_messages.append(
                    ToolMessage(
                        content=f"Erreur : {str(e)}",
                        tool_call_id=tool_call["id"]
                    )
                )

    return {
        **state,
        "messages": state["messages"] + new_messages,
        "reasoning_logs": state["reasoning_logs"] + new_logs,
        "step_count": step,
    }


def should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        tool_names = [tc["name"] for tc in last_message.tool_calls]
        irreversible = ["send_email", "schedule_meeting"]
        if any(name in irreversible for name in tool_names):
            return "checkpoint"
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


# ─── CONSTRUCTION DU GRAPH ─────────────────────────────────────────────────────

def build_graph(llm_with_tools):
    graph = StateGraph(AgentState)

    graph.add_node("agent", make_agent_node(llm_with_tools))
    graph.add_node("tools", tools_node)
    graph.add_node("checkpoint", checkpoint_node)

    graph.set_entry_point("agent")

    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "checkpoint": "checkpoint",
            "end": END
        }
    )

    graph.add_edge("tools", "agent")
    graph.add_edge("checkpoint", END)

    return graph.compile()


# ─── FONCTION PRINCIPALE ───────────────────────────────────────────────────────

async def run_workflow(user_id: str, request: str) -> dict:
    # Initialisation du LLM ici — après que load_dotenv() ait été appelé
    llm = ChatOpenAI(
        model=os.getenv("QWEN_MODEL", "qwen-plus"),
        api_key=os.getenv("QWEN_API_KEY"),
        base_url=os.getenv("QWEN_BASE_URL"),
        temperature=0.1
    )
    llm_with_tools = llm.bind_tools(TOOLS)

    workflow_id = str(uuid.uuid4())

    system_message = HumanMessage(content=f"""Tu es un agent d'automatisation de workflows professionnels.

Ton rôle : analyser les demandes des utilisateurs et les exécuter étape par étape.

RÈGLES IMPORTANTES :
1. Toujours appeler check_for_ambiguity en premier pour analyser la demande
2. Si des informations manquent, appeler clarify_input pour poser une question
3. Exécuter les tools nécessaires dans le bon ordre
4. Être précis et professionnel dans tes réponses

Demande de l'utilisateur : {request}
""")

    initial_state: AgentState = {
        "messages": [system_message],
        "workflow_id": workflow_id,
        "user_id": user_id,
        "reasoning_logs": [],
        "step_count": 0,
        "status": "pending",
        "checkpoint_data": {}
    }

    graph = build_graph(llm_with_tools)
    final_state = graph.invoke(initial_state)

    return {
        "workflow_id": workflow_id,
        "status": final_state["status"],
        "reasoning_logs": final_state["reasoning_logs"],
        "checkpoint_data": final_state.get("checkpoint_data", {}),
        "messages": final_state["messages"]
    }