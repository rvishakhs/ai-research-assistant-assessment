import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from app.core.data_loader import DataStore


@pytest.fixture(scope="session")
def store() -> DataStore:
    return DataStore()


@pytest.fixture
def mock_runner() -> MagicMock:
    runner = MagicMock()
    runner.run = AsyncMock(
        return_value={
            "answer": "DS001 is the Primary Care Diabetes Cohort.",
            "sources": ["DS001"],
            "trace_id": "test-trace-id",
            "tools_invoked": ["get_dataset_metadata"],
            "execution_time_ms": 150.0,
        }
    )
    return runner


@pytest.fixture
def client(mock_runner) -> TestClient:
    from app.main import app

    app.state.runner = mock_runner
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
