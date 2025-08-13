import os
import json
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from src.api.user import router as user_router
from src.api.admin import router as admin_router
from src.api.facebook import router as fb_router
from src.database.checkpointer import get_checkpointer_ctx
from src.graphs.main_graph import create_main_graph
# Unified single marketing graph architecture; travel graph count no longer relevant.

AGENTS_DESCRIPTION_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "src",
    "domain_configs",
    "agents_description.json"
)


debug_router = APIRouter()

@asynccontextmanager
async def lifespan(app: FastAPI):
    with get_checkpointer_ctx() as checkpointer:
        app.state.checkpointer = checkpointer
        app.state.graph = create_main_graph(checkpointer)
        yield

app = FastAPI(lifespan=lifespan)

# app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add user_router
app.include_router(user_router)
app.include_router(admin_router)
app.include_router(fb_router)

@app.get("/agents", response_class=JSONResponse, tags=["Agents"])
async def get_agents():
    """Return the list of chatbot agents and their descriptions."""
    try:

        def load_agents():
            with open(AGENTS_DESCRIPTION_PATH, "r", encoding="utf-8") as f:
                return json.load(f)

        agents = await asyncio.to_thread(load_agents)
        return agents
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"error": f"Failed to load agents: {e}"}
        )


# --- Health Check Endpoint ---
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for Docker containers and load balancers."""
    return {"status": "healthy", "message": "LangGraph Chatbot is running"}



# Deprecated debug endpoint removed (multi-subgraph architecture retired)


app.include_router(debug_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("webapp:app", host="0.0.0.0", port=2024, reload=True)
