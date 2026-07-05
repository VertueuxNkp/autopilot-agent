import asyncio
import websockets
import json

async def test():
    uri = "ws://localhost:8000/ws/test-workflow-123"
    try:
        async with websockets.connect(uri, open_timeout=10) as ws:
            print("Connexion WebSocket établie !")
            await ws.send(json.dumps({"type": "ping"}))
            response = await ws.recv()
            print(f"Réponse : {response}")
    except Exception as e:
        print(f"Erreur : {type(e).__name__} : {e}")

asyncio.run(test())