import pytest
from app.core.governance import GovernanceEngine, NHS_SUPPRESSION_NOTICE, MINIMUM_CELL_COUNT


@pytest.fixture
def engine() -> GovernanceEngine:
    return GovernanceEngine()


def test_suppresses_empty_result(engine):
    result = engine.apply({"rows": []})
    assert result.suppressed is True
    assert result.data is None

def test_suppresses_four_records(engine):
    result = engine.apply({"rows": [{"a": 1}, {"a": 2}, {"a": 3}, {"a": 4}]})
    assert result.suppressed is True

def test_passes_exactly_five_records(engine):
    rows = [{"a": i} for i in range(MINIMUM_CELL_COUNT)]
    result = engine.apply({"rows": rows})
    assert result.suppressed is False
    assert result.data is not None

def test_passes_twenty_records(engine):
    rows = [{"a": i} for i in range(20)]
    result = engine.apply({"rows": rows})
    assert result.suppressed is False

def test_suppression_message_contains_nhs(engine):
    result = engine.apply({"rows": [{"a": 1}]})
    assert "NHS" in result.message

def test_missing_rows_key_is_suppressed(engine):
    result = engine.apply({})
    assert result.suppressed is True