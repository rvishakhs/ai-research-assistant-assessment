from pydantic import BaseModel

class QueryRequest(BaseModel):
    question: str
    researcher_id: str | None = None


class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    trace_id: str
    tools_invoked: list[str]
    execution_time_ms: float
