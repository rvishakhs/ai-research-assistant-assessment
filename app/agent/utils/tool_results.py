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


def tool_call_args_by_id(messages) -> dict[str, dict]:
    """Map each tool_call_id to the args it was invoked with."""
    args_by_id: dict[str, dict] = {}
    for msg in messages:
        if isinstance(msg, AIMessage):
            for call in getattr(msg, "tool_calls", None) or []:
                args_by_id[call["id"]] = call.get("args", {})
    return args_by_id


def items_for_tool(messages, tool_name: str) -> list[dict]:
    return [
        item for item, name in iter_tool_result_items(messages) if name == tool_name
    ]

def _empty_researcher_scoped_project_search_args(messages) -> dict | None:
    args_by_id = tool_call_args_by_id(messages)
    for msg in messages:
        if not isinstance(msg, ToolMessage) or msg.name != "list_projects":
            continue

        args = args_by_id.get(msg.tool_call_id, {})
        if not args.get("researcher_id"):
            continue

        if msg.content == []:
            return args

        saw_payload = False
        item_count = 0
        for text in iter_tool_result_texts(msg):
            try:
                payload = json.loads(text)
            except (TypeError, ValueError):
                continue
            saw_payload = True
            if isinstance(payload, list):
                item_count += len(payload)
            elif isinstance(payload, dict):
                item_count += 1

        if saw_payload and item_count == 0:
            return args
    return None

def _datasets_for_domain(store: DataStore, domain: str) -> list:
    domain_lower = domain.lower()
    dataset_ids: list[str] = []

    for dataset in store.datasets.values():
        if (
            domain_lower in dataset.name.lower()
            or domain_lower in dataset.description.lower()
        ):
            dataset_ids.append(dataset.id)

    for project in store.projects.values():
        if (
            domain_lower in project.organisation.lower()
            or domain_lower in project.title.lower()
        ):
            dataset_ids.extend(project.datasets)

    seen: set[str] = set()
    return [
        store.datasets[dataset_id]
        for dataset_id in dataset_ids
        if dataset_id in store.datasets
        and not (dataset_id in seen or seen.add(dataset_id))
    ]

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