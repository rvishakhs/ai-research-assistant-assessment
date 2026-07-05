from mcp.server.fastmcp import FastMCP

from app.core.data_loader import DataStore
from app.core.governance import GovernanceEngine

mcp = FastMCP("nhs-research-assistant")
_store = DataStore()
_governance = GovernanceEngine()

def _has_full_access(researcher) -> bool:
    """Researchers whose 'projects' list is the wildcard ["*"] can see/query everything."""
    return researcher.projects == ["*"]



@mcp.tool()
def list_projects(
    researcher_id: str | None = None,
) -> list[dict]:
    """Discover All NHS research projects Or with researcher specified."""

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
    """Retrieve full details for a single research project by its ID"""
    project = _store.projects.get(project_id.upper())
    if not project:
        return {"error": f"Project '{project_id}' not found."}
    return project.model_dump()

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


if __name__ == "__main__":
    mcp.run()
