from mcp.server.fastmcp import FastMCP

from app.core.data_loader import DataStore
from app.core.governance import GovernanceEngine

mcp = FastMCP("nhs-research-assistant")
_store = DataStore()
_governance = GovernanceEngine()

def _has_full_access(researcher) -> bool:
    """Researchers whose 'projects' list is the wildcard ["*"] can see/query everything."""
    return researcher.projects == ["*"]

def _researcher_can_query(researcher_id: str, dataset_id: str) -> bool:
    """A restricted dataset is queryable if the researcher has wildcard access,
    or if one of their projects explicitly includes this dataset."""
    researcher = _store.researchers.get(researcher_id)
    if not researcher or _has_full_access(researcher):
        return True
    accessible_dataset_ids = {
        linked_id
        for project_id in researcher.projects
        if project_id in _store.projects
        for linked_id in _store.projects[project_id].datasets
    }
    return dataset_id in accessible_dataset_ids

@mcp.tool()
def list_projects(
    researcher_id: str | None = None,
) -> list[dict]:
    """Discover All NHS research project or by a researcher's username to return only their projects."""
    projects = list(_store.projects.values())

    if researcher_id:
        researcher = _store.researchers.get(researcher_id)

        if not researcher:
            return []

        if not _has_full_access(researcher):
            projects = [
                project
                for project in projects
                if project.id in researcher.projects
            ]

    return [project.model_dump() for project in projects]

@mcp.tool()
def get_project(project_id: str) -> dict:
    """Retrieve full details for a single research project by its ID (e.g. PRJ001)."""
    project = _store.projects.get(project_id.upper())
    if not project:
        return {"error": f"Project '{project_id}' not found."}
    return project.model_dump()


@mcp.tool()
def search_datasets(
    keyword: str,
    include_restricted: bool = False,
) -> list[dict]:
    """Search datasets by keyword matched against name and description. Restricted
    datasets are excluded by default; pass include_restricted=True to include them."""
    keyword_lower = keyword.lower()
    results = []
    for dataset in _store.datasets.values():
        if dataset.restricted and not include_restricted:
            continue
        if keyword_lower in dataset.name.lower() or keyword_lower in dataset.description.lower():
            results.append(dataset.model_dump())
    return results

@mcp.tool()
def get_dataset_metadata(dataset_id: str) -> dict:
    """Retrieve full metadata for a dataset including its field definitions.
    Use this to understand what data a dataset contains before running a query."""
    dataset = _store.datasets.get(dataset_id.upper())
    if not dataset:
        return {"error": f"Dataset '{dataset_id}' not found."}
    return dataset.model_dump()

@mcp.tool()
def run_query(
    dataset_id: str,
    researcher_id: str | None = None,
) -> dict:
    """Execute an analytical query against a dataset. Returns sample rows or a
    governance suppression notice if the result set contains fewer than 5 records.
    Restricted datasets require explicit researcher authorisation."""
    dataset_id = dataset_id.upper()
    dataset = _store.datasets.get(dataset_id)
    if not dataset:
        return {"error": f"Dataset '{dataset_id}' not found."}

    if dataset.restricted and researcher_id and not _researcher_can_query(researcher_id, dataset_id):
        return {
            "error": (
                f"Researcher '{researcher_id}' is not authorised to query "
                f"restricted dataset '{dataset_id}'."
            )
        }

    query_result = _store.query_results.get(dataset_id)
    if not query_result:
        return {"error": f"No sample query results available for '{dataset_id}'."}

    verdict = _governance.apply(query_result)
    if verdict.suppressed:
        return {"suppressed": True, "governance_notice": verdict.message}

    return {
        "dataset_id": dataset_id,
        "count": query_result["count"],
        "rows": query_result["rows"],
    }

if __name__ == "__main__":
    mcp.run()
