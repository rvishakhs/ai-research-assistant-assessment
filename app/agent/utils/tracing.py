def trace_config(trace_id: str, researcher_id: str | None) -> dict:
    """Attach non-sensitive metadata for optional LangSmith/LangChain tracing.

    Tracing is disabled unless the deployment sets LANGSMITH_TRACING and a
    LangSmith API key. The raw question and model/tool messages are still part
    of LangChain traces when tracing is enabled, so hosted tracing should not be
    enabled for confidential data without approval/redaction.
    """
    return {
        "run_name": "nhs_research_assistant_query",
        "tags": ["nhs-research-assistant"],
        "metadata": {
            "trace_id": trace_id,
            "has_researcher_id": researcher_id is not None,
        },
    }
