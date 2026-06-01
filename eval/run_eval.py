"""CLI for the golden-set evaluation. Uses whichever LLM provider is configured
(heuristic by default; OpenAI when TRIAGE_LLM_PROVIDER=openai + a key).

    uv run python eval/run_eval.py
"""

import asyncio

from triage.conversations.repositories.seeded_customer_repository import SeededCustomerRepository
from triage.conversations.services.enrichment import make_enricher
from triage.core.config import get_settings
from triage.evaluation import evaluate, load_cases
from triage.providers.factory import make_llm_provider


async def _main() -> None:
    settings = get_settings()
    provider = make_llm_provider(settings)
    report = await evaluate(
        load_cases(), provider, make_enricher(SeededCustomerRepository())
    )
    print(f"provider:            {type(provider._inner).__name__}")
    print(f"scenarios:           {report['n']}")
    print(f"routing accuracy:    {report['routing_accuracy']:.0%}")
    print(f"escalation accuracy: {report['escalation_accuracy']:.0%}")
    print("-" * 72)
    for r in report["rows"]:
        mark = "OK  " if r["owner_ok"] else "MISS"
        print(f"  [{mark}] expected={r['expected']:<22} got={r['got']:<22} {r['message']}")


if __name__ == "__main__":
    asyncio.run(_main())
