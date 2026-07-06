import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class AuditRecord(BaseModel):
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    question: str
    researcher_id: str | None = None
    tools_invoked: list[str] = Field(default_factory=list)
    execution_time_ms: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: str | None = None
