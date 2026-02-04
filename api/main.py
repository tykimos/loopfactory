from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import agents, pending, metrics, factory, activity, system

app = FastAPI(title="LoopFactory MCN", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents.router)
app.include_router(pending.router)
app.include_router(metrics.router)
app.include_router(factory.router)
app.include_router(activity.router)
app.include_router(system.router)

@app.get("/health")
async def health():
    return {"status": "ok"}
