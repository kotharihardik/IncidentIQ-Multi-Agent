import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers.incidents import router as incidents_router

app = FastAPI(
    title="IncidentIQ — Multi-Agent Incident Analysis",
    description="AI-powered root cause analysis and fix recommendation system.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(incidents_router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=False,
    )
