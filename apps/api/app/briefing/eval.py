"""Run the summarizer against fixed multi-source stories and report how well it is grounded.

    python -m app.briefing.eval ../../evals/briefing/cases.jsonl

Needs Ollama running with LLM_MODEL pulled. "Grounded" means it survived validation; read the
printed summaries too, because validation catches invented numbers, not every wrong claim.
"""

import asyncio
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

from app.briefing.llm import get_llm_client
from app.briefing.summarize import SourceText, summarize
from app.core.config import settings


def _sources(case: dict) -> list[SourceText]:
    return [
        SourceText(
            s["source_name"],
            s["title"],
            datetime.fromisoformat(s["published_at"]) if s.get("published_at") else None,
            s["text"],
        )
        for s in case["sources"]
    ]


async def main(path: Path) -> None:
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    llm = get_llm_client()
    print(f"model={llm.model_name} cases={len(cases)}\n")

    first_try = fallbacks = dropped = injected = 0
    latencies: list[int] = []
    for case in cases:
        result = await summarize(llm, _sources(case), settings.summary_source_chars)
        output = " ".join([result.headline, *(b.text for b in result.bullets)]).lower()
        hits = [term for term in case.get("forbidden", []) if term in output]

        first_try += result.method == "llm" and result.attempts == 1
        fallbacks += result.method == "extractive"
        dropped += result.dropped_bullets
        injected += bool(hits)
        latencies.append(result.latency_ms)

        print(f"[{case['id']}] {result.method} attempts={result.attempts} "
              f"dropped={result.dropped_bullets} {result.latency_ms} ms")
        print(f"  {result.headline}")
        for bullet in result.bullets:
            print(f"  - {bullet.text} {bullet.citations}")
        for error in result.errors:
            print(f"  ! {error}")
        if hits:
            print(f"  ! INJECTION: output contains {hits}")
        print()

    count = len(cases)
    print(f"grounded on first try: {first_try}/{count}")
    print(f"fell back to extractive: {fallbacks}/{count}")
    print(f"bullets dropped by validation: {dropped}")
    print(f"injection leaks: {injected}/{count}")
    print(f"latency p50={statistics.median(latencies):.0f} ms max={max(latencies)} ms")


if __name__ == "__main__":
    default = "../../evals/briefing/cases.jsonl"
    asyncio.run(main(Path(sys.argv[1] if len(sys.argv) > 1 else default)))
