

def check_sources(expected: list[str], actual: list[str]) -> tuple[bool, str]:
    actual_set = {s.upper() for s in actual}
    missing = [s for s in expected if s.upper() not in actual_set]
    if missing:
        return False, f"missing expected sources: {missing} (got {actual})"
    return True, ""


def check_keywords(expected: list[str], answer: str) -> tuple[bool, str]:
    answer_lower = answer.lower()
    missing = [kw for kw in expected if kw.lower() not in answer_lower]
    if missing:
        return False, f"missing expected keywords: {missing}"
    return True, ""
