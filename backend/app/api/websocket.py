import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict

router = APIRouter()

# ─── GESTIONNAIRE DE CONNEXIONS ────────────────────────────────────────────────
class ConnectionManager:
    """
    Gère toutes les connexions WebSocket actives.
    Un workflow_id peut avoir plusieurs connexions (ex: plusieurs onglets).
    """
    def __init__(self):
        self.active_connections: Dict[str, list[WebSocket]] = {}

    async def connect(self, workflow_id: str, websocket: WebSocket):
        await websocket.accept()
        if workflow_id not in self.active_connections:
            self.active_connections[workflow_id] = []
        self.active_connections[workflow_id].append(websocket)
        print(f"[WS] Connexion établie pour workflow {workflow_id}")

    def disconnect(self, workflow_id: str, websocket: WebSocket):
        if workflow_id in self.active_connections:
            self.active_connections[workflow_id].remove(websocket)
            if not self.active_connections[workflow_id]:
                del self.active_connections[workflow_id]
        print(f"[WS] Connexion fermée pour workflow {workflow_id}")

    async def send_log(self, workflow_id: str, log: dict):
        """Envoie un log à tous les clients connectés pour ce workflow"""
        if workflow_id in self.active_connections:
            message = json.dumps(log)
            for websocket in self.active_connections[workflow_id]:
                try:
                    await websocket.send_text(message)
                except Exception:
                    pass

    async def send_status(self, workflow_id: str, status: str, data: dict = {}):
        """Envoie un changement de statut au frontend"""
        if workflow_id in self.active_connections:
            message = json.dumps({
                "type": "status_update",
                "workflow_id": workflow_id,
                "status": status,
                "data": data
            })
            for websocket in self.active_connections[workflow_id]:
                try:
                    await websocket.send_text(message)
                except Exception:
                    pass


# Instance globale du gestionnaire
manager = ConnectionManager()


# ─── ENDPOINT WEBSOCKET ────────────────────────────────────────────────────────
@router.websocket("/ws/{workflow_id}")
async def websocket_endpoint(websocket: WebSocket, workflow_id: str):
    """
    M4 se connecte ici pour recevoir les logs en temps réel.
    La connexion reste ouverte pendant toute la durée du workflow.
    """
    await manager.connect(workflow_id, websocket)
    try:
        # Garder la connexion ouverte et écouter les messages de M4
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # M4 peut envoyer un ping pour vérifier que la connexion est active
            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        manager.disconnect(workflow_id, websocket)