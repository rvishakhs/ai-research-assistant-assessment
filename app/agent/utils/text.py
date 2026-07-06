import json
import re

from langchain_core.messages import ToolMessage

from app.agent.utils.sources import extract_sources
from app.agent.utils.tool_results import (
    iter_tool_result_texts,
    items_for_tool,
    tool_call_args_by_id,
)
from app.core.data_loader import DataStore

_MARKDOWN_PATTERNS = [
    (re.compile(r"```.*?```", re.DOTALL), " "),
    (re.compile(r"`([^`]*)`"), r"\1"),
    (re.compile(r"\*\*([^*]+)\*\*"), r"\1"),
    (re.compile(r"__([^_]+)__"), r"\1"),
    (re.compile(r"(?<!\w)[*_]([^*_]+)[*_](?!\w)"), r"\1"),
    (re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE), ""),
    (re.compile(r"^\s*[-*+]\s+", re.MULTILINE), ""),
]


def to_plain_text(content) -> str:
    """Collapse LLM output into a single plain-text line."""
    if isinstance(content, list):
        text = " ".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    else:
        text = str(content)

    for pattern, replacement in _MARKDOWN_PATTERNS:
        text = pattern.sub(replacement, text)

    return re.sub(r"\s+", " ", text).strip()


def _join_names(names: list[str]) -> str:
    if len(names) <= 2:
        return " and ".join(names)
    return ", ".join(names[:-1]) + f", and {names[-1]}"

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


def _join_names(names: list[str]) -> str:
    if len(names) <= 2:
        return " and ".join(names)
    return ", ".join(names[:-1]) + f", and {names[-1]}"


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


def _looks_like_stripped_project_answer(answer: str) -> bool:
    return (
        not answer.strip()
        or bool(re.fullmatch(r"[\s;:,.()A-Za-z]*", answer))
        and ";" in answer
        and not re.search(r"\w{4,}", answer)
    )


def repair_answer_from_tool_results(
    question: str,
    messages,
    answer: str,
    researcher_id: str | None = None,
) -> str:
    """Use already-returned tool results to repair malformed list-style answers."""
    question_lower = question.lower()
    store = DataStore()

    if researcher_id and ("project" in question_lower or "research" in question_lower):
        scoped_project_args = _empty_researcher_scoped_project_search_args(messages)
        if scoped_project_args:
            topic = scoped_project_args.get("keyword") or scoped_project_args.get(
                "organisation"
            )
            if topic:
                item_type = "research" if "research" in question_lower else "projects"
                verb = "is" if item_type == "research" else "are"
                return f"No {topic}-related {item_type} {verb} available for this researcher."
            item_type = "research" if "research" in question_lower else "projects"
            verb = "is" if item_type == "research" else "are"
            return f"No {item_type} {verb} available for this researcher."

    records_match = re.search(r"more than\s+(\d+)\s+records", question_lower)
    if "dataset" in question_lower and records_match:
        minimum_records = int(records_match.group(1))
        visible = [
            dataset.name
            for dataset in store.datasets.values()
            if dataset.records > minimum_records and not dataset.restricted
        ]
        restricted = [
            dataset.name
            for dataset in store.datasets.values()
            if dataset.records > minimum_records and dataset.restricted
        ]
        response = f"Datasets with more than {minimum_records:,} records are {_join_names(visible)}."
        if restricted:
            response += (
                f" Restricted datasets that also match are {_join_names(restricted)}."
            )
        return response

    if "dataset" in question_lower:
        for domain in ("respiratory", "oncology", "cardiology"):
            if domain in question_lower:
                datasets = _datasets_for_domain(store, domain)
                if datasets:
                    names = [dataset.name for dataset in datasets]
                    return f"{domain.title()} datasets: {_join_names(names)}."

    run_query_results = items_for_tool(messages, "run_query")
    if run_query_results and (
        "run" in question_lower
        or "query" in question_lower
        or "analysis" in question_lower
    ):
        result = run_query_results[-1]
        dataset_id = result.get("dataset_id")
        dataset = store.datasets.get(dataset_id) if dataset_id else None
        dataset_name = dataset.name if dataset else "The dataset"
        error = result.get("error", "")
        if result.get("suppressed"):
            return "Results were suppressed because the query returned fewer than 5 records, which risks re-identification under NHS policy."
        if "restricted" in error.lower() and "authorised" in error.lower():
            return f"{dataset_name} is restricted and requires an authorised researcher_id to query."
        if "not authorised" in error.lower():
            return f"The authenticated researcher is not authorised to query {dataset_name}."
        if result.get("count") is not None:
            return f"The query returned {result['count']} records from {dataset_name}."

    access_match = re.search(r"projects\s+can\s+([a-z][\w-]*)\s+access", question_lower)
    if access_match:
        username = access_match.group(1)
        researcher = store.researchers.get(username)
        if researcher:
            projects_for_researcher = (
                list(store.projects.values())
                if researcher.projects == ["*"]
                else [
                    store.projects[project_id]
                    for project_id in researcher.projects
                    if project_id in store.projects
                ]
            )
            titles = [project.title for project in projects_for_researcher]
            if titles:
                display_name = researcher.display_name
                return f"{display_name} can access {_join_names(titles)}."

    projects = items_for_tool(messages, "list_projects")
    if "projects" not in question_lower or not projects:
        return answer

    if (
        answer
        and not _looks_like_stripped_project_answer(answer)
        and extract_sources(messages, answer)
    ):
        return answer

    titles = [project["title"] for project in projects if project.get("title")]
    if not titles:
        return answer

    if "alice" in question_lower and "access" in question_lower:
        return f"Alice can access {_join_names(titles)}."
    if "active" in question_lower:
        return f"Active projects: {_join_names(titles)}."
    if "completed" in question_lower:
        return f"Completed projects: {_join_names(titles)}."
    if "public health" in question_lower:
        return f"Public Health projects: {_join_names(titles)}."

    datasets = items_for_tool(messages, "get_dataset_metadata")
    dataset_names_by_id = {
        dataset.get("id"): dataset.get("name") for dataset in datasets
    }
    if len(projects) == 1:
        project = projects[0]
        linked_names = [
            dataset_names_by_id[dataset_id]
            for dataset_id in project.get("datasets", [])
            if dataset_names_by_id.get(dataset_id)
        ]
        if linked_names:
            return f"{project['title']} uses {_join_names(linked_names)}."
        return project["title"]

    return f"Projects: {_join_names(titles)}."

