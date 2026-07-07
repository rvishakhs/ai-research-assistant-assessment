import json
from app.core.data_loader import DataStore
from langchain_core.messages import AIMessage, ToolMessage


# Tools whose results are a browse/search over many candidate records. FastMCP's
# stdio transport serialises a list[dict] tool return as one separate content
# block per item, so the tool name is the reliable browse/direct-lookup signal.
_BROWSE_TOOLS = {"list_projects", "search_datasets", "list_researchers"}

def iter_tool_result_texts(msg: ToolMessage):
    """Yield text blocks from a ToolMessage across supported content shapes."""
    content = msg.content
    if isinstance(content, str):
        yield content
    elif isinstance(content, list):
        for block in content:
            if (
                isinstance(block, dict)
                and block.get("type") == "text"
                and "text" in block
            ):
                yield block["text"]
            elif isinstance(block, str):
                yield block


def iter_tool_result_items(messages):
    """Yield (item, tool_name) for each dict found in tool result payloads."""
    for msg in messages:
        if not isinstance(msg, ToolMessage):
            continue
        for text in iter_tool_result_texts(msg):
            try:
                payload = json.loads(text)
            except (TypeError, ValueError):
                continue
            items = payload if isinstance(payload, list) else [payload]
            for item in items:
                if isinstance(item, dict):
                    yield item, msg.name

def extract_sources(messages, answer: str) -> list[str]:
    """Identify which dataset/project/researcher IDs the final answer refers to."""
    answer_lower = answer.lower()
    sources: list[str] = []
    seen: set[str] = set()

    def add(candidate_id: str, is_username: bool) -> None:
        normalised = candidate_id if is_username else candidate_id.upper()
        if normalised not in seen:
            seen.add(normalised)
            sources.append(normalised)

    def cited(candidate_id: str, label: str | None) -> bool:
        return candidate_id.lower() in answer_lower or (
            bool(label) and label.lower() in answer_lower
        )

    for item, tool_name in iter_tool_result_items(messages):
        is_username = (
            "id" not in item
            and "dataset_id" not in item
            and "project_id" not in item
            and "username" in item
        )
        item_id = (
            item.get("id")
            or item.get("dataset_id")
            or item.get("project_id")
            or item.get("username")
        )
        if not item_id:
            continue
        label = item.get("name") or item.get("title") or item.get("display_name")

        if tool_name not in _BROWSE_TOOLS:
            add(item_id, is_username)
            continue

        if cited(item_id, label):
            add(item_id, is_username)

    store = DataStore()
    for project in store.projects.values():
        if project.title.lower() in answer_lower:
            add(project.id, is_username=False)
    for dataset in store.datasets.values():
        if dataset.name.lower() in answer_lower:
            add(dataset.id, is_username=False)
    for researcher in store.researchers.values():
        if researcher.display_name.lower() in answer_lower:
            add(researcher.username, is_username=True)

    return sources