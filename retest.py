"""CLI tool for automated retesting, mitigation validation, and comparative reporting."""

import argparse
import asyncio
import sys
from typing import List, Optional
import httpx

from app.northwind.config import get_settings
from app.northwind.guardrails.manager import GuardrailManager
from engine.orchestrator.retest_comparator import RetestComparator
from engine.orchestrator.runner import AssessmentRunner
from engine.orchestrator.target import BaseTarget, HttpTarget


class RetestDirectTarget(BaseTarget):
    """Direct in-process target applying the designated defense profile."""

    def __init__(self, defense_mode: str = "defense_in_depth"):
        self.defense_mode = defense_mode
        self.manager = GuardrailManager()

    async def send_prompt(self, prompt: str):
        res = await self.manager.process_chat(
            user_message=prompt,
            defense_mode=self.defense_mode,
        )
        return {
            "response": res["text"],
            "model": res["model"],
            "latency_ms": res["latency_ms"],
            "telemetry": res.get("telemetry"),
        }


class RetestHttpTarget(BaseTarget):
    """HTTP target explicitly requesting the designated defense profile."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000", defense_mode: str = "defense_in_depth"):
        self.base_url = base_url.rstrip("/")
        self.defense_mode = defense_mode

    async def is_healthy(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.base_url}/health")
                return res.status_code == 200
        except Exception:
            return False

    async def set_server_defense_mode(self):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{self.base_url}/defense",
                    json={"defense_mode": self.defense_mode},
                )
        except Exception:
            pass

    async def send_prompt(self, prompt: str):
        url = f"{self.base_url}/chat"
        payload = {"message": prompt, "defense_mode": self.defense_mode}
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(url, json=payload)
            res.raise_for_status()
            data = res.json()
            return {
                "response": data["response"],
                "model": data.get("model", "unknown"),
                "latency_ms": data.get("latency_ms", 0.0),
                "telemetry": data.get("telemetry"),
            }


async def main():
    parser = argparse.ArgumentParser(
        description="SentinelForge — Retest mitigations and verify vulnerability remediation."
    )
    parser.add_argument(
        "--mode",
        default="defense_in_depth",
        choices=["none", "input_only", "prompt_hardening", "output_only", "defense_in_depth"],
        help="Defense profile to test (default: defense_in_depth).",
    )
    parser.add_argument(
        "--tests",
        default=None,
        help="Comma-separated test IDs to retest (e.g. 'SE-001,SE-004'). If omitted, retests entire suite.",
    )
    parser.add_argument(
        "--target-url",
        default=None,
        help="Base URL of running Northwind API.",
    )
    parser.add_argument(
        "--direct",
        action="store_true",
        help="Execute retest directly in-process without requiring an active HTTP server.",
    )
    parser.add_argument(
        "--pacing",
        type=float,
        default=0.5,
        help="Delay between requests in seconds.",
    )
    args = parser.parse_args()

    settings = get_settings()

    # Determine Target
    if args.direct:
        target = RetestDirectTarget(defense_mode=args.mode)
        print(f"[*] Retesting in DIRECT mode with defense profile: '{args.mode}'")
    else:
        url = args.target_url or f"http://{settings.app_host}:{settings.app_port}"
        http_target = RetestHttpTarget(base_url=url, defense_mode=args.mode)
        is_up = await http_target.is_healthy()
        if not is_up:
            print(f"[!] Server at {url} is not responding. Falling back to direct in-process target...")
            target = RetestDirectTarget(defense_mode=args.mode)
        else:
            await http_target.set_server_defense_mode()
            target = http_target
            print(f"[*] Connected to {url}. Server defense profile set to '{args.mode}'.")

    from pathlib import Path
    retest_ev_dir = Path(__file__).resolve().parent / "results" / "retest"
    runner = AssessmentRunner(target=target, evidence_dir=retest_ev_dir, pacing_delay_sec=args.pacing)
    all_attacks = runner.load_attacks()

    # Filter attacks if specified
    if args.tests:
        requested_ids = [t.strip().upper() for t in args.tests.split(",")]
        attacks_to_run = [a for a in all_attacks if a["id"].upper() in requested_ids]
        if not attacks_to_run:
            print(f"[-] Error: None of requested IDs {requested_ids} found in dataset.")
            return 1
    else:
        attacks_to_run = all_attacks

    print("=================================================================")
    print("  SentinelForge — Automated Retest & Remediation Verification")
    print("=================================================================")
    print(f"Defense Profile:  {args.mode.upper()}")
    print(f"Probes Selected:  {len(attacks_to_run)} scenarios")
    print("-----------------------------------------------------------------")
    print("Executing Retest Suite...")
    print("-----------------------------------------------------------------")

    retest_results = []
    for idx, attack in enumerate(attacks_to_run, start=1):
        outcome = await runner.run_single_attack(attack)
        retest_results.append(outcome)
        
        # Pacing
        if args.pacing > 0 and idx < len(attacks_to_run):
            await asyncio.sleep(args.pacing)

        score = outcome["score"]
        status_icon = "✅ PASS" if score.passed else "❌ FAIL"
        test_id = attack["id"]
        test_name = attack.get("name", "")[:32]
        print(f"[{idx:02d}/{len(attacks_to_run):02d}] {test_id:<8} {test_name:<32} ........ {status_icon}")

    # Comparative analysis against baseline evidence
    comparator = RetestComparator()
    comparison_summary = comparator.compare_and_generate_report(
        retest_results=retest_results,
        defense_mode=args.mode,
    )

    print("\n-----------------------------------------------------------------")
    print("Retest & Remediation Summary")
    print("-----------------------------------------------------------------")
    print(f"Total Retested:        {comparison_summary['total_retested']}")
    print(f"Vulnerabilities Fixed: {comparison_summary['remediated']} 🛡️")
    print(f"Persistent Failures:   {comparison_summary['persistent']}")
    print(f"Regressions:           {comparison_summary['regressions']}")
    print(f"Maintained Secure:     {comparison_summary['maintained_secure']}")
    print(f"Remediation Rate:      {comparison_summary['remediation_rate']}%")
    print(f"Verification Report:   {comparison_summary['report_path']}")
    print("=================================================================\n")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
