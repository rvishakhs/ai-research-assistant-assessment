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


class GovernanceEngine:
    def apply(self, query_result: dict) -> GovernanceResult:
        rows = query_result.get("rows", [])
        if len(rows) < MINIMUM_CELL_COUNT:
            return GovernanceResult(
                suppressed=True,
                data=None,
                message=NHS_SUPPRESSION_NOTICE,
            )
        return GovernanceResult(suppressed=False, data=query_result, message=None)
