"""Evidence collection and persistence engine for reproducible security findings."""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, Optional
from core.scorers.base import ScoreResult


class EvidenceCollector:
    """Packages test execution artifacts and saves JSON evidence to disk."""

    def __init__(self, output_dir: Optional[Path] = None):
        if output_dir is None:
            # Default to results/evidence relative to project root
            project_root = Path(__file__).resolve().parent.parent.parent
            self.output_dir = project_root / "results" / "evidence"
        else:
            self.output_dir = Path(output_dir)

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def record_evidence(
        self,
        test_case: Dict[str, Any],
        prompt: str,
        response_text: str,
        score_result: ScoreResult,
        model_name: str,
        target_name: str = "Northwind Chatbot",
        latency_ms: float = 0.0,
    ) -> Dict[str, Any]:
        """Compile a verifiable evidence dictionary and write it to JSON."""
        test_id = test_case["id"]
        evidence_data = {
            "test_id": test_id,
            "name": test_case.get("name", ""),
            "category": test_case.get("category", "unknown"),
            "severity": test_case.get("severity", "MEDIUM"),
            "owasp_category": test_case.get("owasp_category", "Unspecified"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target": target_name,
            "model": model_name,
            "latency_ms": latency_ms,
            "prompt": prompt.strip(),
            "response": response_text.strip(),
            "secret_detected": score_result.secret_detected,
            "prompt_leak_detected": score_result.prompt_leak_detected,
            "violations": score_result.violations,
            "result": "PASS" if score_result.passed else "FAIL",
            "scoring_details": score_result.details,
            "reproduction_command": f"python reproduce.py {test_id}",
        }

        output_file = self.output_dir / f"{test_id}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(evidence_data, f, indent=2, ensure_ascii=False)

        return evidence_data

    def load_evidence(self, test_id: str) -> Optional[Dict[str, Any]]:
        """Load an existing evidence file for a given test ID."""
        file_path = self.output_dir / f"{test_id}.json"
        if not file_path.exists():
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

