import json
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from database import engine
import models
from routers import auth, projects, tasks, analytics

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="NeuroTask AI",
    description="AI-Powered Project & Task Management Platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(analytics.router)


class ConnectionManager:
    def __init__(self):
        self.active = {}

    async def connect(self, ws: WebSocket, user_id: int):
        await ws.accept()
        self.active.setdefault(user_id, []).append(ws)

    def disconnect(self, ws: WebSocket, user_id: int):
        if user_id in self.active:
            self.active[user_id] = [c for c in self.active[user_id] if c != ws]

    async def broadcast_to_user(self, user_id: int, message: dict):
        for ws in self.active.get(user_id, []):
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                pass


manager = ConnectionManager()


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(ws: WebSocket, user_id: int):
    await manager.connect(ws, user_id)
    try:
        await ws.send_text(json.dumps({"type": "connected", "message": "Real-time sync active"}))
        while True:
            data = await ws.receive_text()
            await ws.send_text(data)
    except WebSocketDisconnect:
        manager.disconnect(ws, user_id)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "NeuroTask AI", "version": "1.0.0"}


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str):
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
