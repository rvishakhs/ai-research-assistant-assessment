import json
import logging
import re
import sys
import time
import uuid

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI

from app.agent.prompts import build_system_prompt
from app.agent.graph import SYSTEM_PROMPT, AgentState, build_graph
from app.core.audit import AuditRecord
from app.core.config import settings


logger = logging.getLogger(__name__)

class AgentRunner:
    """Main runner class managing the agent and its dependencies"""
    def __init__(self):
        self._graph = None
        self._client: MultiServerMCPClient | None = None
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



    async def run_query(self, query: str, researcher_id: str | None = None) -> dict:
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
            final_state = await self._graph.ainvoke(initial_state)
        except Exception as exc:
            error = str(exc)
            logger.exception("Agent graph raised an exception for trace %s", trace_id)

        elapsed_ms = (time.monotonic() - started_at) * 1000
        tools_invoked = final_state["tools_invoked"] if final_state else []

        audit = AuditRecord(
            trace_id=trace_id,
            query=query,
            researcher_id=researcher_id,
            tools_invoked=tools_invoked,
            execution_time_ms=round(elapsed_ms, 2),
            error=error,
        )
        logger.info("AUDIT %s", audit.model_dump_json())

        if error:
            raise RuntimeError(error)

        answer = _to_plain_text(final_state["messages"][-1].content)
        sources = _extract_sources(final_state["messages"])

        return {
            "answer": answer,
            "sources": sources,
            "trace_id": trace_id,
            "tools_invoked": _avoid_duplicates_in_tool_invoked(tools_invoked),
            "execution_time": round(elapsed_ms, 2),
        }

def _avoid_duplicates_in_tool_invoked(items: list[str]) -> list[str]:
    """This function is used to remove duplicate entries for the tool invoked list"""
    seen: set[str] = set()
    result: list[str] = []

    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)

    return result

_MARKDOWN_PATTERNS = [
    (re.compile(r"```.*?```", re.DOTALL), " "),
    (re.compile(r"`([^`]*)`"), r"\1"),
    (re.compile(r"\*\*([^*]+)\*\*"), r"\1"),
    (re.compile(r"__([^_]+)__"), r"\1"),
    (re.compile(r"(?<!\w)[*_]([^*_]+)[*_](?!\w)"), r"\1"),
    (re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE), ""),
    (re.compile(r"^\s*[-*+]\s+", re.MULTILINE), ""),
]

def _to_plain_text(content) -> str:
    """Collapse LLM output (markdown, multi-block content) into a single plain-text line."""
    if isinstance(content, list):
        text = " ".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    else:
        text = str(content)

    for pattern, replacement in _MARKDOWN_PATTERNS:
        text = pattern.sub(replacement, text)

    return re.sub(r"\s+", " ", text).strip()

def _iter_tool_result_texts(msg: ToolMessage):
    """Yield each text block from a ToolMessage, handling both str and list-of-dict content shapes."""
    content = msg.content
    if isinstance(content, str):
        yield content
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text" and "text" in block:
                yield block["text"]
            elif isinstance(block, str):
                yield block


def _extract_sources(messages) -> list[str]:
    """Extract dataset/project IDs from tool call results."""
    sources: list[str] = []
    seen: set[str] = set()

    def add(candidate_id: str | None) -> None:
        if candidate_id and candidate_id.upper() not in seen:
            seen.add(candidate_id.upper())
            sources.append(candidate_id.upper())

    for msg in messages:
        if not isinstance(msg, ToolMessage):
            continue
        for text in _iter_tool_result_texts(msg):
            try:
                payload = json.loads(text)
            except (TypeError, ValueError):
                continue
            items = payload if isinstance(payload, list) else [payload]
            for item in items:
                if not isinstance(item, dict):
                    continue
                add(item.get("id"))
                add(item.get("dataset_id"))
                add(item.get("project_id"))

    return sources

