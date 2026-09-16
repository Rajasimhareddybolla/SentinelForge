#!/usr/bin/env python3
"""CLI runner for executing Microsoft PyRIT multi-turn adversarial campaigns in SentinelForge."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.northwind.client import GroqClient
from app.northwind.config import get_settings
from app.northwind.guardrails.manager import GuardrailManager
from engine.orchestrator.target import DirectTarget, HttpTarget
from integrations.pyrit.runner import PyritScannerAdapter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_pyrit")


def print_banner(mode: str, target_type: str, model: str):
    print("=" * 80)
    print("  SENTINELFORGE - MICROSOFT PyRIT MULTI-TURN RED-TEAMING SCANNER")
    print("=" * 80)
    print(f"  Target Mode:     {mode.upper()}")
    print(f"  Target Type:     {target_type}")
    print(f"  Underlying LLM:  {model}")
    print("=" * 80)
    print()


def print_results_summary(results: dict):
    summary = results["summary"]
    print("\n" + "=" * 80)
    print("  PyRIT SCAN EXECUTION SUMMARY")
    print("=" * 80)
    print(f"  Scan ID:                  {results['scan_id']}")
    print(f"  Defense Profile:          {results['defense_mode']}")
    print(f"  Total Campaigns Run:      {summary['total_campaigns']}")
    print(f"  Total Dialogue Turns:     {summary['total_turns']}")
    print(f"  Compromised Campaigns:    {summary['compromised_campaigns']}")
    print(f"  Contained Campaigns:      {summary['remediated_campaigns']}")
    print(f"  Attack Success Rate:      {summary['attack_success_rate']:.1f}%")
    print("-" * 80)
    print("  Invariants Tested:")
    for inv in summary["invariants_tested"]:
        print(f"    • {inv}")
    print("-" * 80)
    print("  Campaign Breakdown:")
    for c in results["campaigns"]:
        status = "🔴 COMPROMISED" if c["compromised"] else "🟢 CONTAINED"
        turn_str = f"earliest turn {c['earliest_turn_compromised']}" if c["compromised"] else "all turns safe"
        print(f"    [{status}] {c['campaign_id']} - {c['name']} ({turn_str})")
    print("=" * 80)
    print(f"  Report saved to: results/pyrit_report.md")
    print("=" * 80 + "\n")


async def main():
    parser = argparse.ArgumentParser(
        description="Run PyRIT automated multi-turn adversarial red-teaming assessment."
    )
    parser.add_argument(
        "--mode",
        choices=["none", "input_only", "prompt_hardening", "output_only", "defense_in_depth"],
        default="defense_in_depth",
        help="Target defense mode to evaluate (default: defense_in_depth)",
    )
    parser.add_argument(
        "--direct",
        action="store_true",
        default=False,
        help="Use direct in-process target with GuardrailManager instead of HTTP server",
    )
    parser.add_argument(
        "--target-url",
        default="http://127.0.0.1:8000",
        help="Base URL of running Northwind API if not using --direct (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--campaign",
        default=None,
        help="Specific campaign ID to run (e.g. MT-CRESCENDO-PII-001)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to save JSON evidence (default: results/pyrit)",
    )
    parser.add_argument(
        "--fail-on-compromise",
        action="store_true",
        default=False,
        help="Exit with non-zero code if any campaign was compromised",
    )

    args = parser.parse_args()
    settings = get_settings()

    if args.direct:
        groq_client = GroqClient(settings=settings)
        manager = GuardrailManager(groq_client=groq_client)
        target = DirectTarget(groq_client=groq_client, guardrail_manager=manager)
        target_type = "In-Process Direct Target (GuardrailManager)"
    else:
        target = HttpTarget(base_url=args.target_url)
        target_type = f"HTTP Target ({args.target_url})"
        if not await target.is_healthy():
            logger.warning(
                "HTTP target at %s is not reachable. Falling back to direct in-process target.",
                args.target_url,
            )
            groq_client = GroqClient(settings=settings)
            manager = GuardrailManager(groq_client=groq_client)
            target = DirectTarget(groq_client=groq_client, guardrail_manager=manager)
            target_type = "In-Process Direct Target (Auto-Fallback)"

    print_banner(mode=args.mode, target_type=target_type, model=settings.groq_model)

    adapter = PyritScannerAdapter()
    results = await adapter.run_scan(
        target=target,
        options={
            "defense_mode": args.mode,
            "campaign_id": args.campaign,
            "output_dir": args.output_dir,
        },
    )

    print_results_summary(results)

    if args.fail_on_compromise and results["summary"]["compromised_campaigns"] > 0:
        logger.error(
            "Security threshold breached: %d campaign(s) compromised under defense mode '%s'!",
            results["summary"]["compromised_campaigns"],
            args.mode,
        )
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

