from typing import Annotated, Callable, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

SYSTEM_PROMPT = """You are an AI Research Assistant for an NHS Research and Analytics Platform.

Your role is to help researchers discover projects, explore datasets, and retrieve
analytical results. You have access to the following tools:
- list_projects: discover research projects, optionally filtered by status or researcher
- get_project: retrieve full details for a project by ID
- search_datasets: search datasets by keyword
- get_dataset_metadata: retrieve dataset metadata and field definitions
- run_query: execute an analytical query against a dataset

Dataset and project IDs are already returned separately to the researcher alongside
your answer, so do not repeat them inline (e.g. do not write "DS001" or "(Dataset ID:
DS001)" in your prose) — refer to items by name only. If a governance suppression
notice is returned, state in one short sentence that the results were suppressed and
why (e.g. fewer than 5 records) — do not suggest how to proceed unless the researcher
asks.

Answer as briefly as possible: a single short sentence for simple lookups. Only
include extra detail (fields, record counts, descriptions, or suggestions) if the
researcher's question specifically asks for it.

Respond in plain text only: no markdown formatting (no headers, bullet points,
bold/italics, or code blocks) and no line breaks.
"""


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    trace_id: str
    tools_invoked: list[str]
    start_time: float
    error: str | None


def build_graph(llm_with_tools, tools: list):
    """Compile a LangGraph StateGraph for the NHS research assistant agent."""

    async def agent_node(state: AgentState) -> dict:
        response = await llm_with_tools.ainvoke(state["messages"])
        return {"messages": [response]}

    def make_tools_node(tool_list: list) -> Callable[[AgentState], dict]:
        tool_executor = ToolNode(tool_list)

        async def tools_node(state: AgentState) -> dict:
            result = await tool_executor.ainvoke(state)
            invoked = [
                msg.name
                for msg in result.get("messages", [])
                if hasattr(msg, "name") and msg.name
            ]
            return {
                **result,
                "tools_invoked": state["tools_invoked"] + invoked,
            }

        return tools_node

    def should_continue(state: AgentState) -> str:
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            return "tools"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", make_tools_node(tools))
    graph.set_entry_point("agent")
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", END: END},
    )
    graph.add_edge("tools", "agent")

    return graph.compile()
