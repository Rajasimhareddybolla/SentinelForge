"""Reproduce a single security test finding and verify reproducibility."""

import argparse
import asyncio
import sys
from pathlib import Path

from app.northwind.config import get_settings
from engine.evidence.collector import EvidenceCollector
from engine.orchestrator.runner import AssessmentRunner
from engine.orchestrator.target import DirectTarget, HttpTarget


async def main():
    parser = argparse.ArgumentParser(
        description="SentinelForge — Reproduce and verify a specific AI security finding."
    )
    parser.add_argument("test_id", help="The test ID to reproduce (e.g., PI-001, SE-001, SPE-001)")
    parser.add_argument(
        "--target-url",
        default=None,
        help="Base URL of running Northwind API (e.g. http://127.0.0.1:8000).",
    )
    parser.add_argument(
        "--direct",
        action="store_true",
        help="Run attack directly in-process against Groq API.",
    )
    args = parser.parse_args()

    settings = get_settings()

    if args.direct:
        target = DirectTarget()
    else:
        url = args.target_url or f"http://{settings.app_host}:{settings.app_port}"
        http_target = HttpTarget(url)
        is_up = await http_target.is_healthy()
        if not is_up:
            print(f"[*] Target server at {url} not reachable. Using direct in-process target...")
            target = DirectTarget()
        else:
            target = http_target

    runner = AssessmentRunner(target=target)
    attacks = runner.load_attacks()
    
    # Find matching attack
    target_attack = None
    for a in attacks:
        if a["id"].upper() == args.test_id.upper():
            target_attack = a
            break

    if not target_attack:
        print(f"[-] Error: Test ID '{args.test_id}' not found in attack datasets.")
        print(f"    Available IDs: {', '.join(a['id'] for a in attacks)}")
        return 1

    print("=================================================================")
    print(f"  SentinelForge — Attack Reproduction: {target_attack['id']}")
    print("=================================================================")
    print(f"Name:        {target_attack.get('name', '')}")
    print(f"Category:    {target_attack.get('category', '')}")
    print(f"Severity:    {target_attack.get('severity', '')}")
    print(f"OWASP Class: {target_attack.get('owasp_category', '')}")
    print("-----------------------------------------------------------------")
    print("Adversarial Prompt Sent:")
    print(target_attack["prompt"].strip())
    print("-----------------------------------------------------------------")

    outcome = await runner.run_single_attack(target_attack)
    score = outcome["score"]

    print("Target Response:")
    print(outcome["response"].strip())
    print("-----------------------------------------------------------------")
    print("Scoring Verdict:")
    print(f"Result:            {'❌ FAIL (Vulnerability Confirmed)' if not score.passed else '✅ PASS (Attack Blocked)'}")
    print(f"Secret Disclosed:  {'TRUE' if score.secret_detected else 'FALSE'}")
    print(f"Prompt Leaked:     {'TRUE' if score.prompt_leak_detected else 'FALSE'}")
    if score.violations:
        print(f"Violations:        {', '.join(score.violations)}")
    print(f"Latency:           {outcome['latency_ms']} ms")
    print(f"Evidence Saved:    results/evidence/{target_attack['id']}.json")
    print("=================================================================")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

