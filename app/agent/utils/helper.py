import logging
import sys
import time
import uuid

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI

from app.agent.graph import AgentState, build_graph
from app.agent.prompts import build_system_prompt
from app.core.audit import AuditRecord
from app.core.config import settings

logger = logging.getLogger(__name__)


class AgentRunner:
    """Manages the lifecycle of the MCP subprocess and the LangGraph agent."""

    def __init__(self) -> None:
        self._client: MultiServerMCPClient | None = None
        self._graph = None
        self._system_prompt: str | None = None

    async def start(self) -> None:
        self._client = MultiServerMCPClient(
            {
                "nhs": {
                    "command": sys.executable,
                    "args": ["-m", "app.mcp_server.server"],
                    "transport": "stdio",
                }
            }
        )
        tools = await self._client.get_tools()
        self._system_prompt = build_system_prompt(tools)
        llm = self._build_llm()
        self._graph = build_graph(llm.bind_tools(tools), tools)
        logger.info("AgentRunner started. %d MCP tools loaded.", len(tools))

    @staticmethod
    def _build_llm() -> ChatOpenAI:
        llm_kwargs: dict = {
            "model": settings.openai_model,
            "api_key": settings.openai_api_key,
        }
        if settings.openai_model.startswith("gpt-5"):
            llm_kwargs["reasoning_effort"] = "minimal"
        return ChatOpenAI(**llm_kwargs)

    async def stop(self) -> None:
        logger.info("AgentRunner stopped.")

    async def run(self, question: str, researcher_id: str | None = None) -> dict:
        trace_id = str(uuid.uuid4())
        started_at = time.monotonic()

        messages = [SystemMessage(content=self._system_prompt or "")]

        if researcher_id:
            messages.append(
                SystemMessage(
                    content=(
                        f"The authenticated researcher making this request is "
                        f"'{researcher_id}'. Pass researcher_id='{researcher_id}' to "
                        "any tool call that accepts a researcher_id parameter "
                        "(list_projects, run_query), even if the question does not "
                        "name the researcher explicitly."
                    )
                )
            )
        messages.append(HumanMessage(content=question))

        initial_state: AgentState = {
            "messages": messages,
            "trace_id": trace_id,
            "tools_invoked": [],
            "start_time": started_at,
            "error": None,
        }

        error: str | None = None
        final_state: AgentState | None = None

        try:
            final_state = await self._graph.ainvoke(
                initial_state,
                config=_trace_config(trace_id, researcher_id),
            )
        except Exception as exc:
            error = str(exc)
            logger.exception("Agent graph raised an exception for trace %s", trace_id)

        elapsed_ms = (time.monotonic() - started_at) * 1000
        tools_invoked = final_state["tools_invoked"] if final_state else []

        audit = AuditRecord(
            trace_id=trace_id,
            question=question,
            researcher_id=researcher_id,
            tools_invoked=tools_invoked,
            execution_time_ms=round(elapsed_ms, 2),
            error=error,
        )
        logger.info("AUDIT %s", audit.model_dump_json())

        if error:
            raise RuntimeError(error)

        answer = _to_plain_text(final_state["messages"][-1].content)
        answer = _ground_answer(final_state["messages"], answer, trace_id)
        answer = _repair_answer_from_tool_results(
            question, final_state["messages"], answer, researcher_id
        )
        sources = _extract_sources(final_state["messages"], answer)

        return {
            "answer": answer,
            "sources": sources,
            "trace_id": trace_id,
            "tools_invoked": _dedupe_preserve_order(tools_invoked),
            "execution_time_ms": round(elapsed_ms, 2),
        }
