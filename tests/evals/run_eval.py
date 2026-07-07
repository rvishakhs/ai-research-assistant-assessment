"""Golden-question evaluation workflow.

Usage:
    uv run python -m tests.eval.run_eval
    uv run python -m tests.eval.run_eval --report eval_report.json
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.agent.agentrunner import AgentRunner
from tests.evals.checks import check_keywords, check_sources

GOLDEN_PATH = Path(__file__).parent / "golden.json"


async def run() -> list[dict]:
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))

    runner = AgentRunner()
    await runner.start()

    results = []
    try:
        for case in golden:
            question = case["question"]
            try:
                result = await runner.run(question)
                sources_ok, sources_reason = check_sources(
                    case.get("expected_sources", []), result["sources"]
                )
                keywords_ok, keywords_reason = check_keywords(
                    case.get("must_contain", []), result["answer"]
                )
                passed = sources_ok and keywords_ok
                reasons = [r for r in (sources_reason, keywords_reason) if r]
                results.append(
                    {
                        "question": question,
                        "passed": passed,
                        "answer": result["answer"],
                        "sources": result["sources"],
                        "reasons": reasons,
                    }
                )
            except Exception as exc:  # noqa: BLE001 - want to keep evaluating remaining questions
                results.append(
                    {
                        "question": question,
                        "passed": False,
                        "answer": None,
                        "sources": [],
                        "reasons": [f"runner raised: {exc}"],
                    }
                )
    finally:
        await runner.stop()

    return results


def print_report(results: list[dict]) -> None:
    passed = sum(1 for r in results if r["passed"])
    total = len(results)

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"[{status}] {r['question']}")
        if not r["passed"]:
            for reason in r["reasons"]:
                print(f"        {reason}")
            print(f"        answer: {r['answer']!r}")

    print(f"\n{passed}/{total} questions passed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report", type=Path, default=None, help="Optional path to write a JSON report to."
    )
    args = parser.parse_args()

    results = asyncio.run(run())
    print_report(results)

    if args.report:
        args.report.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"Report written to {args.report}")

    if any(not r["passed"] for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()