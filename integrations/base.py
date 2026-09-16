"""Base scanner adapter interface for external red-teaming tool integrations in SentinelForge.

Enables modular integration of Microsoft PyRIT, Garak, and Promptfoo while normalizing
all findings, scoring, telemetry, and evidence into the unified SentinelForge data schema.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("sentinelforge.integrations")


class BaseScannerAdapter(ABC):
    """Unified adapter protocol that all third-party security scanners must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Identifier of the scanner tool (e.g., 'pyrit', 'garak', 'promptfoo')."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Short human-readable summary of the scanner's focus and capabilities."""
        pass

    @abstractmethod
    async def run_scan(
        self,
        target: Any,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute the security scanner campaign and return normalized SentinelForge results.

        Args:
            target: The target instance under test (e.g., BaseTarget, HttpTarget, DirectTarget).
            options: Optional configuration overrides (e.g., defense_mode, campaigns, output_dir).

        Returns:
            Dict conforming to the standard SentinelForge scan schema.
        """
        pass

    def save_evidence(
        self,
        scan_results: Dict[str, Any],
        output_dir: Optional[Path] = None,
    ) -> Path:
        """Saves scan results to JSON in the specified directory."""
        project_root = Path(__file__).resolve().parent.parent
        out_dir = Path(output_dir or (project_root / "results" / self.name))
        out_dir.mkdir(parents=True, exist_ok=True)

        scan_id = scan_results.get("scan_id", f"{self.name}_{int(datetime.now().timestamp())}")
        output_path = out_dir / f"{scan_id}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(scan_results, f, indent=2)

        logger.info("Saved %s scan results to %s", self.name, output_path)
        return output_path

    def generate_report_markdown(self, scan_results: Dict[str, Any]) -> str:
        """Renders standard Markdown report summarizing findings from this scan."""
        summary = scan_results.get("summary", {})
        campaigns = scan_results.get("campaigns", [])
        scan_id = scan_results.get("scan_id", "N/A")
        tool = scan_results.get("tool", self.name)
        mode = scan_results.get("defense_mode", "unknown")
        timestamp = scan_results.get("timestamp", datetime.now(timezone.utc).isoformat())

        md = [
            f"# {tool.upper()} Red-Teaming Assessment Report",
            "",
            f"**Scan ID:** `{scan_id}`  ",
            f"**Tool Integration:** {tool}  ",
            f"**Defense Profile:** `{mode}`  ",
            f"**Timestamp:** `{timestamp}`  ",
            f"**Target Model:** `{scan_results.get('target_model', 'unknown')}`  ",
            "",
            "## Executive Summary",
            "",
            f"- **Total Campaigns Run:** {summary.get('total_campaigns', len(campaigns))}",
            f"- **Total Multi-Turn Dialogues:** {summary.get('total_turns', 0)}",
            f"- **Compromised Campaigns:** {summary.get('compromised_campaigns', 0)}",
            f"- **Contained Campaigns:** {summary.get('remediated_campaigns', 0)}",
            f"- **Attack Success Rate (ASR):** {summary.get('attack_success_rate', 0.0):.1f}%",
            "",
            "### Tested Invariants & Risk Categories",
            "",
        ]

        for inv in summary.get("invariants_tested", []):
            md.append(f"- {inv}")

        md.extend([
            "",
            "## Campaign Findings & Dialogue Traces",
            "",
        ])

        for c in campaigns:
            status = "🔴 COMPROMISED (VULNERABLE)" if c.get("compromised") else "🟢 CONTAINED (PROTECTED)"
            md.extend([
                f"### Campaign: {c.get('name', 'Unnamed Campaign')} — {status}",
                f"- **Category:** `{c.get('category', 'unknown')}`",
                f"- **Turns Executed:** {c.get('turns_executed', 0)}",
                f"- **Earliest Turn Compromised:** {c.get('earliest_turn_compromised', 'None')}",
                f"- **Summary:** {c.get('summary', 'No summary provided')}",
                "",
                "#### Conversation Dialogue Trace",
                "",
            ])

            for turn in c.get("turns", []):
                t_idx = turn.get("turn_index", 0)
                role_attack = turn.get("user_prompt", "")
                resp = turn.get("response", "")
                passed = turn.get("score_passed", True)
                turn_status = "DEFENDED (NO LEAK)" if passed else "COMPROMISED (INVARIANT LEAK)"

                md.extend([
                    f"**Turn {t_idx} [{turn_status}]**",
                    f"- **Attacker Technique / Intent:** *{turn.get('technique', 'Adversarial Prompt')}*",
                    f"- **User Prompt:**",
                    "```text",
                    role_attack,
                    "```",
                    f"- **Model Response:**",
                    "```text",
                    resp,
                    "```",
                ])

                if turn.get("violations"):
                    md.append(f"- **Violations Detected:** {', '.join(turn['violations'])}")
                if turn.get("telemetry"):
                    telem = turn["telemetry"]
                    md.append(f"- **Guardrail Telemetry:** Input Intercepted={telem.get('input_intercepted')}, Output Intercepted={telem.get('output_intercepted')}")
                md.append("")

        return "\n".join(md)

