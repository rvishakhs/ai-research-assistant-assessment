import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.agent.agentrunner import AgentRunner
from app.api.routes import router

logging.basicConfig(
    level=logging.INFO,
    format = "%(asctime)s %(levelname)s %(name)s — %(message)s",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    runner = AgentRunner()
    await runner.start()
    app.state.runner = runner
    yield
    await runner.stop()

app = FastAPI(
    title="NHS AI Research Assistant",
    description="AI-powered assistant for NHS research project and dataset discovery",
    version="0.1.0",
    lifespan=lifespan,
)


app.include_router(router)