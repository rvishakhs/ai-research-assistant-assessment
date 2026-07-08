# **NHS AI Research Assistant** 

## Contents
1. Project overview
2. Architecture
3. Technologies used
4. Folder structure
5. Assumptions
6. Setup instructions
7. Known limitations
8. Future improvements

### Project overview
An AI-Powered research assistant for the NHS research and Analytics Platform. Researcher can discover projects, explore datasets, and run approved analytical queries through a conversial natural language interface. Key capabilities include project/dataset discovery, dataset metadata retrieval, governed query execution, researcher lookup, audit logging.

**Key Features**
- **Single-agent, ReAct-style architecture**. I chose a single LangGraph agent instead of a multi-agent setup because the application is mainly coordinating tool calls rather than solving complex reasoning tasks. The agent decides which tool to use, observes the result, and continues until it has enough information to answer the user. This keeps the architecture simpler, reduces latency, and makes the workflow easier to understand and debug.
- **MCP as the data access layer.** The agent never talks to databases or datasets directly. Instead, it interacts with the MCP server, which exposes the available tools. MCP automatically injects the tool definitions into the agent's system prompt, so the agent always knows what tools it can use. If new tools are added to the MCP server, they become available to the agent without changing its core logic. Keeping MCP as a separate service also makes it easier to scale, secure, and reuse with other applications in the future.
- **Server-side governance.** Data governance is enforced inside the MCP tool layer rather than relying on prompts or the LLM. Every request goes through the governance engine before data is returned, ensuring that suppression rules and access policies cannot be bypassed through prompt manipulation. The governance engine is policy-based, making it easy to add new rules without modifying the agent or API.
- **Role-based access control.** Access is determined by the researcher's assigned projects. Researchers with projects = ["*"] have full access, while others can only query datasets linked to their projects. If a request does not include a valid researcher_id, access to restricted datasets is denied. This ensures that sensitive data is only available to authorised users.

### Architecture

```
Client
  │  POST /query
  ▼
FastAPI (app/main.py, app/api/routes.py)
  ▼
AgentRunner (app/agent/agentrunner.py)
  │  builds a LangGraph ReAct agent bound to MCP tools
  ▼
LangGraph agent/tools loop (app/agent/graph.py)
  │  OpenAI LLM decides which tools to call, in what order
  ▼
MCP client (langchain-mcp-adapters, MultiServerMCPClient)
  │  stdio subprocess
  ▼
MCP server (app/mcp_server/server.py, FastMCP)
  │  list_projects, get_project, search_datasets, get_dataset_metadata,
  │  run_query, list_researchers, get_researcher
  ▼
DataStore (app/core/data_loader.py)          — in-memory singleton over the research data
  ▼
GovernanceEngine (app/core/governance.py)    — pluggable policies, e.g. MinimumCellCountPolicy
  ▼
AuditRecord (app/core/audit.py)              — trace_id, tools_invoked, execution_time_ms, errors
  ▼
Evaluation (pytest and golden-datset)        — 45+ test cases and 25 evaluation questions

```
### Technology Choices

| Technology          | Choice       | Reason                                                                                                                                                                                         |
| ------------------- | ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Agent Framework** | LangGraph    | Provides explicit state management with complete control over the agent workflow. Makes it easy to track metadata such as `tools_invoked`, `trace_id`, and other execution state across nodes. |
| **Backend / API**   | FastAPI      | High-performance asynchronous web framework with native `async/await` support, automatic request validation using Pydantic, and a lightweight architecture.                                    |
| **Language Model**  | OpenAI GPT-5 | Reliable, industry-standard language model for agentic workflows with strong tool-calling and reasoning capabilities.                                                                          |
| **MCP Server**      | FastMCP      | Simplifies building MCP servers and automatically exposes tool definitions to the agent, making it easy to add new tools while keeping data access separated from the agent logic.             |
| **Package Manager** | uv           | Fast, lightweight dependency manager with significantly quicker package installation and                                                                                                       |


### Folder Structure

```
.
├── app/
│   ├── main.py                  # FastAPI app + lifespan (starts/stops the AgentRunner)
│   ├── api/
│   │   └── routes.py            # GET /health, POST /query
│   ├── schemas/
│   │   └── api.py               # QueryRequest / QueryResponse models
│   ├── core/
│   │   ├── config.py            # environment-driven settings
│   │   ├── data_loader.py       # DataStore: in-memory singleton over research data
│   │   ├── models.py            # Dataset / Project / Researcher models
│   │   ├── governance.py        # GovernanceEngine + governance policies
│   │   └── audit.py             # AuditRecord model
│   ├── mcp_server/
│   │   ├── server.py            # MCP server exposing the research platform's tools
│   │   └── utils/helper.py      # access-control and ID-resolution helpers
│   └── agent/
│       ├── agentrunner.py       # wires up the MCP client and the LangGraph agent per request
│       ├── graph.py             # LangGraph agent/tools loop
│       ├── prompts.py           # system prompt and tool-summary builder
│       └── utils/               # answer formatting and source extraction helpers
├── mock-data/                    # research data: projects, datasets, researchers, query results
├── tests/
│   ├── test_app.py               # API-level tests
│   ├── test_runner.py            # governance/policy tests
│   ├── test_tools.py             # MCP tool tests
│   └── evals/                    # golden-question, end-to-end evaluation harness
├── pyproject.toml
├── uv.lock
├── .env.example
├── Dockercompose.yml
└── DockerFile

```

### Assumptions
- **Single-agent architecture:** A single Langgraph agent is sufficient for the described use cases. Multi-agent adds complexity with benefit at this scale
- **In-memory data:** DataStore is a singleton service, loads all JSON files once at startup. This is appropriate for the mock data size. databases will be considered for production and when data scales
- **Audit logging:** Currently audit logging is managed to trackdown the workflow, in production level application it need to be stored in a database for validation 
- **Governance Applied at Tool level** In this Architecture governance applies directly at tool level to make it imposibble for LLM prompts to bypass. 

### Setup instructions

**Prerequisites**

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- An OpenAI API key

**Setup**

```bash
# install dependencies
uv sync

# configure environment
cp .env.example .env
# edit .env and set OPENAI_API_KEY

# start the API
uv run uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.


**Running tests**

```bash
# unit tests (fast, deterministic — API, governance, MCP tools)
uv run pytest

# end-to-end evaluation suite (exercises the real LLM against golden questions)
uv run python -m tests.evals.run_eval --report tests/evals/eval-report.json
```

#### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes | — | API key used to call the OpenAI model powering the agent. |
| `OPENAI_MODEL` | No | `gpt-5` | OpenAI model used by the agent. |

> Note: LangSmith tracing sends request/response data to a hosted service. Do not enable it against
> confidential data without appropriate approval and redaction.

#### Docker Instructions

Build and run the application in a container:

```bash
# build the image
docker build -t nhs-research-assistant .

# run the container
docker run --env-file .env -p 8000:8000 nhs-research-assistant
```

The API will be available at `http://localhost:8000`, exactly as in local development.

#### API Endpoints

#### `GET /health`

Health check for the service.

**Response**

```json
{"status": "ok"}
```

#### `POST /query`

Submit a natural language question to the research assistant.

**Request body**

```json
{
  "question": "Which datasets are available for diabetes research?",
  "researcher_id": "RS001"
}
```

- `question` (string, required) — the researcher's natural language question.
- `researcher_id` (string, optional) — identifies the requesting researcher, used to enforce
  access control on restricted datasets. If omitted, access to restricted data is denied.

**Response body**

```json
{
  "answer": "One dataset is available for diabetes research: Primary Care Diabetes Cohort.",
  "sources": ["DS001"],
  "trace_id": "a1b2c3d4",
  "tools_invoked": ["search_datasets"],
  "execution_time_ms": 842.5
}
```

### Known Limitations
- **No Streaming output:** `Post/query` endpoint waits until the full agent response is ready. SSE Streaming is the better way to stream the tokens while model generating in the background.
- **In-Process MCP Server:** The MCP server is not shared platform service yet. it currently runs as a sub-process of the FASTAPI server. I did stdio based MCP communication particularly for this project because for this use case it only connect with single agent under our current application. developing MCP server as a seperate service would introduce HTTP communication, exposed ports, service discovery and authentication for data privacy. For the current project uses case it didn't want that complexity.
- **No-researcher-Auth:** No proper auth methods data validations used for researcher
- **In-memory JSON Dict** Currently for Data storing used in-memory singleton service, that is based on the data-size available and to avoid extra complexity for no major benefits. Production level application requires a database for better processing and to protect data.
- **Evaluation and Monitering** Used minimal evaluation functions to keep the application simple 


### Future Improvements
- **Persistent audit log** — write AuditRecord to PostgreSQL for compliance reporting
- **Streaming responses** — Server-Sent Events for real-time token delivery
- **Authentication middleware** — JWT validation for researcher_id
- **Rate limiting** — per-researcher query throttling
- **Additional governance rules** — field-level redaction, time-window access controls
- **Evaluation harness** — automated scoring against evaluation_questions.json