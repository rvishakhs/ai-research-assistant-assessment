from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

def build_graph(llm, tools):
    async def chatbot(state: AgentState):
        response = await llm.ainvoke(state["messages"])
        return {
            "messages": [response],
        }
    graph = StateGraph(AgentState)

    graph.add_node("chatbot", chatbot)
    graph.set_entry_point("chatbot")
    graph.add_edge("chatbot", END)

    return graph.compile()
