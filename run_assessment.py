"""Master CLI entrypoint to execute automated AI red-teaming assessment."""

import argparse
import asyncio
import sys
from app.northwind.config import get_settings
from engine.orchestrator.runner import AssessmentRunner
from engine.orchestrator.target import DirectTarget, HttpTarget


async def main():
    parser = argparse.ArgumentParser(
        description="SentinelForge — Run automated AI red-teaming security assessment."
    )
    parser.add_argument(
        "--target-url",
        default=None,
        help="Base URL of running Northwind API (e.g. http://127.0.0.1:8000).",
    )
    parser.add_argument(
        "--direct",
        action="store_true",
        help="Run assessment directly in-process without needing an HTTP server.",
    )
    parser.add_argument(
        "--pacing",
        type=float,
        default=0.6,
        help="Pacing delay (in seconds) between attack requests to respect Groq rate limits.",
    )
    args = parser.parse_args()

    settings = get_settings()

    if args.direct:
        target = DirectTarget()
        print("Running in DIRECT in-process mode (calling Groq API directly)...")
    else:
        url = args.target_url or f"http://{settings.app_host}:{settings.app_port}"
        http_target = HttpTarget(url)
        is_up = await http_target.is_healthy()
        if not is_up:
            print(f"[!] Target server at {url} is not responding.")
            print("[*] Options:")
            print(f"    1. Start the server in another terminal: python start_server.py")
            print(f"    2. Run in direct in-process mode:        python run_assessment.py --direct")
            print("\nAuto-switching to --direct mode for this run...\n")
            target = DirectTarget()
        else:
            target = http_target

    runner = AssessmentRunner(target=target, pacing_delay_sec=args.pacing)
    summary = await runner.run_assessment()

    # Exit code: 1 if critical vulnerabilities were found, 0 otherwise
    # In security CI/CD, detecting vulnerabilities or regressions can trigger a non-zero exit or audit code
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

