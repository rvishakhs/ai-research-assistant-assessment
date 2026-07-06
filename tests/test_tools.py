import pytest

from app.mcp_server.server import (
    get_dataset_metadata,
    get_project,
    get_researcher,
    list_projects,
    list_researchers,
    run_query,
    search_datasets,
)

# list project tool based test cases
def test_list_all_projects():
    result = list_projects()
    assert len(result) == 20

def test_active_projects():
    result = list_projects(status='Active')
    assert len(result) == 15
    assert all(p["status"] == "Active" for p in result )

def test_completed_projects():
    result = list_projects('Completed')
    assert len(result) == 5
    assert all(p["status"] == "Completed" for p in result)

def test_list_all_projects_case_sensitive():
    result = list_projects(status='active')
    assert len(result) == 15

def test_list_project_by_researcher_charlie():
    result = list_projects(researcher_id="charlie")
    ids = [p["id"] for p in result]
    assert "PRJ015" in ids
    assert "PRJ019" in ids
    assert len(ids) == 2

def test_list_projects_admin_sees_all():
    result = list_projects(researcher_id="admin")
    assert len(result) == 20

def test_list_projects_to_unknown_researcher():
    result = list_projects(researcher_id="nobody")
    assert len(result) == 0 or result == []

def test_list_projects_organisation_no_match():
    result = list_projects(organisation="Astrophysics")
    assert result == []

def test_list_projects_by_keyword_title_match():
    """ICU has no matching organisation, but PRJ019's title contains it."""
    result = list_projects(keyword="ICU")
    ids = {p["id"] for p in result}
    assert ids == {"PRJ019"}

def test_list_projects_by_keyword_case_insensitive():
    result = list_projects(keyword="icu")
    ids = {p["id"] for p in result}
    assert ids == {"PRJ019"}


# get_project tool based test cases
def test_get_project_prj001():
    result = get_project("prj001")
    assert result['id'] == "PRJ001"
    assert result["title"] == "Early Detection of Type 2 Diabetes"
    assert result["status"] == "Active"

def test_get_project_case_insensitive():
    result = get_project("prj001")
    assert result["id"] == "PRJ001"

def test_get_project_by_exact_title():
    result = get_project("Early Detection of Type 2 Diabetes")
    assert result["id"] == "PRJ001"

def test_get_project_by_partial_title():
    result = get_project("Type 2 Diabetes")
    assert result["id"] == "PRJ001"

def test_get_project_not_found():
    result = get_project("PRJ999")
    assert "error" in result

def test_get_project_invalid_name_not_found():
    result = get_project("Project ABC123")
    assert "error" in result


# Dataset related test Cases
def test_search_datasets_diabetes():
    result = search_datasets("diabetes")
    ids = [d["id"] for d in result]
    assert "DS001" in ids

def test_search_datasets_excludes_restricted_by_default():
    result = search_datasets("stroke")
    assert all(not d["restricted"] for d in result)

def test_search_datasets_no_match():
    result = search_datasets("zzznomatch")
    assert result == []

def test_search_datasets_no_keyword_returns_all_non_restricted():
    result = search_datasets()
    assert len(result) == 16
    assert all(not d["restricted"] for d in result)


def test_search_datasets_restricted_only():
    result = search_datasets(restricted_only=True)
    ids = {d["id"] for d in result}
    assert ids == {"DS005", "DS010", "DS015", "DS020"}

def test_search_datasets_min_records():
    result = search_datasets(min_records=20000)
    ids = {d["id"] for d in result}
    # Restricted datasets (DS010, DS020) are excluded by default even if they qualify.
    assert ids == {"DS001", "DS004", "DS009", "DS012", "DS013", "DS019"}

def test_search_datasets_max_records():
    result = search_datasets(max_records=100, include_restricted=True)
    assert result == []


# get-project_metadata related test cases
def test_get_dataset_metadata_ds001():
    result = get_dataset_metadata("DS001")
    assert result["id"] == "DS001"
    assert "patient_age" in result["fields"]

def test_get_dataset_metadata_ds003_fields():
    result = get_dataset_metadata("DS003")
    assert "fev1" in result["fields"]
    assert "smoking_status" in result["fields"]

def test_get_dataset_metadata_not_found():
    result = get_dataset_metadata("DS999")
    assert "error" in result


# run-query and governance related test cases
def test_run_query_ds005_unauthorised_named_researcher():
    result = run_query("DS005", researcher_id="bob")
    assert "error" in result
    assert "not authorised" in result["error"]
    assert result["dataset_id"] == "DS005"


def test_run_query_ds001_is_not_suppressed():
    result = run_query("DS001")
    assert result.get("suppressed") is not True
    assert "rows" in result
    assert result["count"] == 18
    assert result["dataset_id"] == "DS001"


def test_run_query_unknown_dataset():
    result = run_query("DS999")
    assert "error" in result


def test_run_query_case_insensitive():
    result = run_query("ds001")
    assert "rows" in result


def test_run_query_by_dataset_name():
    result = run_query("Primary Care Diabetes Cohort")
    assert result["dataset_id"] == "DS001"

# List researcher related test cases
def test_list_researchers_all():
    result = list_researchers()
    assert len(result) == 15


def test_list_researchers_by_role():
    result = list_researchers(role="Platform Administrator")
    assert len(result) >= 1
    assert all(r["role"] == "Platform Administrator" for r in result)
    assert any(r["username"] == "admin" for r in result)


def test_list_researchers_by_partial_role():
    """Real role is 'Platform Administrator'; a shorter guess like
    'Administrator' must still match via substring, since the LLM won't always
    know the exact stored role string."""
    result = list_researchers(role="Administrator")
    assert any(r["username"] == "admin" for r in result)


def test_get_researcher_alice():
    result = get_researcher("alice")
    assert result["username"] == "alice"
    assert result["display_name"] == "Alice Nguyen"


def test_get_researcher_not_found():
    result = get_researcher("nobody")
    assert "error" in result

