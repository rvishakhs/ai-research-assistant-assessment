from typing import Protocol
from dataclasses import dataclass

NHS_SUPPRESSION_NOTICE = (
    "Results suppressed under NHS information governance policy. "
    "The result set contained fewer than 5 records, which risks individual re-identification."
)

MINIMUM_CELL_COUNT = 5


@dataclass
class GovernanceResult:
    suppressed: bool
    data: dict | None
    message: str | None


class MinimumCellCountPolicy:
    def apply(self, query_result: dict) -> GovernanceResult | None:
        rows = query_result.get("rows", [])
        if len(rows) < MINIMUM_CELL_COUNT:
            return GovernanceResult(
                suppressed=True,
                data=None,
                message=NHS_SUPPRESSION_NOTICE,
            )
        return None


class GovernancePolicy(Protocol):
    def apply(self, query_result: dict) -> GovernanceResult | None: ...


class GovernanceEngine:
    def __init__(self, policies: list[GovernancePolicy] | None = None):
        self.policies = policies or [MinimumCellCountPolicy()]

    def apply(self, query_result: dict) -> GovernanceResult:
        for policy in self.policies:
            result = policy.apply(query_result)
            if result is not None:
                return result

        return GovernanceResult(
            suppressed=False,
            data=query_result,
            message=None,
        )
