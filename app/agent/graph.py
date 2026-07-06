from typing import Annotated, Callable, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode


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
