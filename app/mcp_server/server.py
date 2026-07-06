from mcp.server.fastmcp import FastMCP

from app.core.data_loader import DataStore
from app.core.governance import GovernanceEngine
from app.mcp_server.utils.helper import _has_full_access, _resolve_project_id, _resolve_dataset_id, \
    _researcher_can_query

mcp = FastMCP("nhs-research-assistant")
_store = DataStore()
_governance = GovernanceEngine()

@mcp.tool()
def list_projects(
    status: str | None = None,
    organisation: str | None = None,
    keyword: str | None = None,
    researcher_id: str | None = None,
) -> list[dict]:
    """Discover NHS research projects. Optionally filter by status ('Active' or
    'Completed'), by organisation/department (case-insensitive substring match
    against the project's organisation, e.g. 'Digital Health', 'Cardiology',
    'Public Health' — use this for "which <department/domain> projects" style
    questions instead of guessing from the title), by keyword (case-insensitive
    substring match against the project's title — use this for "projects related
    to <topic>" style questions where the topic may appear in a project's title
    even though it isn't the project's organisation, e.g. "ICU" matching a project
    titled "ICU Outcomes Benchmarking" filed under organisation "Critical Care"),
    and/or by a researcher's username to return only their projects."""
    projects = list(_store.projects.values())
    original_projects = projects

    if status:
        projects = [
            project for project in projects if project.status.lower() == status.lower()
        ]

    if organisation:
        organisation_lower = organisation.lower()
        projects = [
            project
            for project in projects
            if organisation_lower in project.organisation.lower()
        ]
        if not projects and not keyword:
            projects = [
                project
                for project in original_projects
                if organisation_lower in project.title.lower()
            ]
            if status:
                projects = [
                    project
                    for project in projects
                    if project.status.lower() == status.lower()
                ]

    if keyword:
        keyword_lower = keyword.lower()
        projects = [
            project for project in projects if keyword_lower in project.title.lower()
        ]

    if researcher_id:
        researcher = _store.researchers.get(researcher_id)
        if not researcher:
            return []
        if not _has_full_access(researcher):
            projects = [
                project for project in projects if project.id in researcher.projects
            ]

    return [project.model_dump() for project in projects]


@mcp.tool()
def get_project(project_id: str) -> dict:
    """Retrieve full details for a single research project by its ID (e.g. PRJ001)
    or its exact/partial title. Always call this to check whether a specific
    project ID or name is valid — if it returns an error, the project does not
    exist and you should say so rather than falling back to list_projects."""
    resolved_id = _resolve_project_id(project_id)
    if not resolved_id:
        return {"error": f"Project '{project_id}' not found."}
    return _store.projects[resolved_id].model_dump()


@mcp.tool()
def search_datasets(
    keyword: str | None = None,
    include_restricted: bool = False,
    restricted_only: bool = False,
    min_records: int | None = None,
    max_records: int | None = None,
) -> list[dict]:
    """Search/filter datasets. All filters are optional and combine with AND:
    - keyword: matched against name and description (case-insensitive substring).
      Omit to match all datasets.
    - include_restricted: include restricted datasets in the results (default False).
    - restricted_only: return only restricted datasets (implies include_restricted).
    - min_records / max_records: filter by the dataset's total record count.
    Use this tool (not run_query) to answer questions like "which datasets are
    restricted?" or "which datasets have more than N records?" — pass restricted_only
    or min_records/max_records instead of guessing via keyword."""
    keyword_lower = keyword.lower() if keyword else None
    show_restricted = include_restricted or restricted_only
    results = []
    for dataset in _store.datasets.values():
        if dataset.restricted and not show_restricted:
            continue
        if restricted_only and not dataset.restricted:
            continue
        if (
            keyword_lower
            and keyword_lower not in dataset.name.lower()
            and keyword_lower not in dataset.description.lower()
        ):
            continue
        if min_records is not None and dataset.records < min_records:
            continue
        if max_records is not None and dataset.records > max_records:
            continue
        results.append(dataset.model_dump())
    return results


@mcp.tool()
def get_dataset_metadata(dataset_id: str) -> dict:
    """Retrieve full metadata for a dataset including its field definitions.
    Accepts a dataset ID (e.g. DS005) or its exact/partial name (e.g. "Stroke
    Recovery Registry") — restricted datasets can still be looked up by name here.
    Use this to understand what data a dataset contains before running a query."""
    resolved_id = _resolve_dataset_id(dataset_id)
    if not resolved_id:
        return {"error": f"Dataset '{dataset_id}' not found."}
    return _store.datasets[resolved_id].model_dump()


@mcp.tool()
def run_query(
    dataset_id: str,
    researcher_id: str | None = None,
) -> dict:
    """Execute an analytical query against a dataset. Accepts a dataset ID (e.g.
    DS005) or its exact/partial name (e.g. "Stroke Recovery Registry"). Returns
    sample rows or a governance suppression notice if the result set contains fewer
    than 5 records. Restricted datasets require an authorised researcher_id — pass
    the researcher_id whenever the caller is known, since restricted datasets cannot
    be queried anonymously."""
    resolved_id = _resolve_dataset_id(dataset_id)
    if not resolved_id:
        return {"error": f"Dataset '{dataset_id}' not found."}
    dataset = _store.datasets[resolved_id]

    if dataset.restricted and not _researcher_can_query(researcher_id, resolved_id):
        if not researcher_id:
            return {
                "error": (
                    f"Dataset '{resolved_id}' is restricted. A researcher_id with "
                    "authorised access is required to query it."
                ),
                "dataset_id": resolved_id,
            }
        return {
            "error": (
                f"Researcher '{researcher_id}' is not authorised to query "
                f"restricted dataset '{resolved_id}'."
            ),
            "dataset_id": resolved_id,
        }

    query_result = _store.query_results.get(resolved_id)
    if not query_result:
        return {
            "error": f"No sample query results available for '{resolved_id}'.",
            "dataset_id": resolved_id,
        }

    verdict = _governance.apply(query_result)
    if verdict.suppressed:
        return {
            "suppressed": True,
            "dataset_id": resolved_id,
            "governance_notice": verdict.message,
        }

    return {
        "dataset_id": resolved_id,
        "count": query_result["count"],
        "rows": query_result["rows"],
    }


@mcp.tool()
def list_researchers(role: str | None = None) -> list[dict]:
    """Discover registered researchers. Optionally filter by role — matched as a
    case-insensitive substring, so 'Administrator' also matches 'Platform
    Administrator'. Use this to answer questions about who has which role or
    access level."""
    researchers = list(_store.researchers.values())
    if role:
        role_lower = role.lower()
        researchers = [r for r in researchers if role_lower in r.role.lower()]
    return [r.model_dump() for r in researchers]


@mcp.tool()
def get_researcher(username: str) -> dict:
    """Retrieve full details for a single researcher by their username (e.g. alice)."""
    researcher = _store.researchers.get(username.lower())
    if not researcher:
        return {"error": f"Researcher '{username}' not found."}
    return researcher.model_dump()


if __name__ == "__main__":
    mcp.run()
