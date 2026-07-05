from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.api.mocks import router as mock_router
from app.api.routes import router as routes_router
from app.api.websocket import router as ws_router

load_dotenv()

app = FastAPI(
    title="Autopilot Agent API",
    description="Backend de l'agent d'automatisation de workflows - Track 4 Qwen Hackathon",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes mockées
app.include_router(mock_router, prefix="/mock")

# Routes réelles
app.include_router(routes_router, prefix="/api")

# WebSocket
app.include_router(ws_router)


@app.get("/")
async def health_check():
    return {
        "status": "ok",
        "message": "Autopilot Agent API is running",
        "version": "1.0.0"
    }