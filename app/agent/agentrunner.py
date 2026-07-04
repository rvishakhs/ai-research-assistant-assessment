from langchain_core.messages import HumanMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI


from app.agent.graph import build_graph
from app.core.config import settings


class AgentRunner:
    def __init__(self):
        self.graph = None

    async def start(self):
        client = MultiServerMCPClient(
            {
                "nhs": {
                    "command": "python",
                    "args": [],
                    "transport": "stdio"
                }
            }
        )

        tools = await client.get_tools()
        llm = ChatOpenAI(
            model = settings.openai_model,
            api_key=settings.openai_api_key,
        )
        llm = llm.bind_tools(tools)

        self.graph = build_graph(llm, tools)

    async def run(self, query: str):
        state = {
            "messages" : [
                HumanMessage(content=query)
            ]
        }

        result = await self.graph.ainvoke(state)

        return result["messages"][-1]["content"]