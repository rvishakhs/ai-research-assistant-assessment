import logging
import re

from langchain_core.messages import ToolMessage

from app.agent.utils.tool_results import (
    iter_tool_result_items,
    iter_tool_result_texts,
    tool_call_args_by_id,
)

logger = logging.getLogger(__name__)

_DATASET_FILTER_KEYS = ("keyword", "min_records", "max_records")

def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result



def _meaningful_dataset_filters(args: dict) -> dict:
    return {key: args[key] for key in _DATASET_FILTER_KEYS if args.get(key) is not None}


def _restricted_call_matches_prior_search(
    args: dict, prior_searches: list[dict]
) -> bool:
    """Check that a restricted-only confirmation used the same real filters."""
    filters = _meaningful_dataset_filters(args)
    prior_filters = [_meaningful_dataset_filters(search) for search in prior_searches]
    filtered_prior_searches = [search for search in prior_filters if search]

    if not filtered_prior_searches:
        return True
    if not filters:
        return False

    return any(
        all(filters.get(key) == value for key, value in prior.items())
        for prior in filtered_prior_searches
    )


def _restricted_only_dataset_count(messages) -> int | None:
    """Return how many datasets a genuine restricted-only search returned."""
    args_by_id = tool_call_args_by_id(messages)
    prior_searches = [
        args for args in args_by_id.values() if not args.get("restricted_only")
    ]
    count: int | None = None
    for msg in messages:
        if not isinstance(msg, ToolMessage) or msg.name != "search_datasets":
            continue
        args = args_by_id.get(msg.tool_call_id, {})
        if not args.get("restricted_only"):
            continue
        if not _restricted_call_matches_prior_search(args, prior_searches):
            continue
        count = (count or 0) + sum(1 for _ in iter_tool_result_texts(msg))
    return count


_RESTRICTED_CLAIM_RE = re.compile(
    r"(\d+)\s+(?:further|additional|more)?\s*restricted\s+\S*\s*datasets?\s+(?:also\s+)?"
    r"(?:match|matched|exist)",
    re.IGNORECASE,
)


def _unfetched_dataset_names(messages) -> set[str]:
    """Return project titles whose linked dataset metadata was not fetched."""
    fetched_dataset_names: set[str] = set()
    fetched_dataset_ids: set[str] = set()
    project_titles: dict[str, str] = {}
    project_dataset_ids: dict[str, list[str]] = {}

    for item, tool_name in iter_tool_result_items(messages):
        if tool_name in {"search_datasets", "get_dataset_metadata", "run_query"}:
            if item.get("name"):
                fetched_dataset_names.add(item["name"])
            if item.get("id"):
                fetched_dataset_ids.add(item["id"])
            if item.get("dataset_id"):
                fetched_dataset_ids.add(item["dataset_id"])
        if (
            tool_name in {"list_projects", "get_project"}
            and item.get("id")
            and item.get("title")
        ):
            project_titles[item["id"]] = item["title"]
            project_dataset_ids[item["id"]] = item.get("datasets", [])

    unfetched: set[str] = set()
    for project_id, title in project_titles.items():
        linked_ids = project_dataset_ids.get(project_id, [])
        if linked_ids and not any(ds_id in fetched_dataset_ids for ds_id in linked_ids):
            unfetched.add(title)
    return unfetched - fetched_dataset_names


def _title_used_as_dataset_name(title: str, answer: str) -> bool:
    """Return True when a project title is labelled as a dataset."""
    for sentence in re.split(r"(?<=[.!?;])\s+", answer):
        if title.lower() not in sentence.lower():
            continue
        sentence_without_title = re.sub(
            re.escape(title), "", sentence, flags=re.IGNORECASE
        ).lower()
        return (
            "dataset" in sentence_without_title
            and "project" not in sentence_without_title
        )
    return False


def ground_answer(messages, answer: str, trace_id: str) -> str:
    """Strip answer claims that are not backed by tool results in this trace."""
    restricted_match = _RESTRICTED_CLAIM_RE.search(answer)
    if restricted_match:
        claimed_count = int(restricted_match.group(1))
        actual_count = _restricted_only_dataset_count(messages)
        if actual_count is None or actual_count != claimed_count:
            logger.warning(
                "Ungrounded restricted-dataset claim stripped for trace %s: "
                "claimed %d, actual %s",
                trace_id,
                claimed_count,
                actual_count,
            )
            sentence_start = max(
                answer.rfind(delimiter, 0, restricted_match.start())
                for delimiter in ".;"
            )
            answer = (
                answer[: sentence_start + 1] if sentence_start != -1 else ""
            ).strip()
            if answer.endswith(";"):
                answer = answer[:-1].rstrip() + "."
            if not answer:
                answer = "No further restricted datasets could be confirmed."

    for title in _unfetched_dataset_names(messages):
        if title.lower() in answer.lower() and _title_used_as_dataset_name(
            title, answer
        ):
            logger.warning(
                "Ungrounded dataset name (unfetched project title '%s') stripped "
                "for trace %s",
                title,
                trace_id,
            )
            answer = re.sub(re.escape(title), "", answer, flags=re.IGNORECASE)
            answer = re.sub(r"\s*,\s*,\s*", ", ", answer)
            answer = re.sub(r"\s+", " ", answer).strip(" ,.")
            if answer and not answer.endswith("."):
                answer += "."

    return answer
