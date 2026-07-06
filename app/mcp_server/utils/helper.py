from app.core.data_loader import DataStore

_store = DataStore()

def _has_full_access(researcher) -> bool:
    """Researchers whose 'projects' list is the wildcard ["*"] can see/query everything."""
    return researcher.projects == ["*"]


def _researcher_can_query(researcher_id: str | None, dataset_id: str) -> bool:
    """A restricted dataset is queryable only if a researcher_id is supplied AND that
    researcher has wildcard access, or one of their projects explicitly includes this
    dataset. No researcher_id means no authorisation — restricted data is never
    accessible anonymously."""
    if not researcher_id:
        return False
    researcher = _store.researchers.get(researcher_id)
    if not researcher:
        return False
    if _has_full_access(researcher):
        return True
    accessible_dataset_ids = {
        linked_id
        for project_id in researcher.projects
        if project_id in _store.projects
        for linked_id in _store.projects[project_id].datasets
    }
    return dataset_id in accessible_dataset_ids


def _resolve_dataset_id(identifier: str) -> str | None:
    """Resolve a dataset ID or exact/partial name (including restricted datasets) to
    its canonical ID. Used by direct-action tools (get_dataset_metadata, run_query)
    where the researcher has already named a specific dataset — discovery-time
    restriction hiding does not apply here, since authorisation is enforced
    separately wherever the data itself is returned."""
    candidate = identifier.strip().upper()
    if candidate in _store.datasets:
        return candidate

    identifier_lower = identifier.strip().lower()
    for dataset in _store.datasets.values():
        if dataset.name.lower() == identifier_lower:
            return dataset.id

    matches = [
        d for d in _store.datasets.values() if identifier_lower in d.name.lower()
    ]
    if len(matches) == 1:
        return matches[0].id
    return None


def _resolve_project_id(identifier: str) -> str | None:
    """Resolve a project ID or exact/partial title to its canonical ID."""
    candidate = identifier.strip().upper()
    if candidate in _store.projects:
        return candidate

    identifier_lower = identifier.strip().lower()
    for project in _store.projects.values():
        if project.title.lower() == identifier_lower:
            return project.id

    matches = [
        p for p in _store.projects.values() if identifier_lower in p.title.lower()
    ]
    if len(matches) == 1:
        return matches[0].id
    return None
