import json

from langchain_core.messages import AIMessage, ToolMessage


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
