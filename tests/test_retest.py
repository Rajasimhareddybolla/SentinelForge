"""Unit tests for RetestComparator and regression tracking."""

import json
from pathlib import Path
import pytest
from core.orchestrator.retest_comparator import RetestComparator
from core.scorers.base import ScoreResult


def test_retest_comparator_classifies_remediated_and_maintained(tmp_path):
    baseline_dir = tmp_path / "baseline"
    baseline_dir.mkdir()
    
    # Fake baseline: SE-001 failed, BEN-001 passed
    (baseline_dir / "SE-001.json").write_text(
        json.dumps({"test_id": "SE-001", "result": "FAIL", "secret_detected": True}),
        encoding="utf-8"
    )
    (baseline_dir / "BEN-001.json").write_text(
        json.dumps({"test_id": "BEN-001", "result": "PASS", "secret_detected": False}),
        encoding="utf-8"
    )

    retest_results = [
        {
            "attack": {"id": "SE-001", "name": "Secret Extraction", "category": "secret-extraction"},
            "score": ScoreResult(passed=True, secret_detected=False),
            "latency_ms": 150.0,
        },
        {
            "attack": {"id": "BEN-001", "name": "Return Policy", "category": "benign-baseline"},
            "score": ScoreResult(passed=True, secret_detected=False),
            "latency_ms": 120.0,
        },
    ]

    comparator = RetestComparator(
        baseline_evidence_dir=baseline_dir,
        results_dir=tmp_path,
    )
    summary = comparator.compare_and_generate_report(retest_results, defense_mode="defense_in_depth")

    assert summary["total_retested"] == 2
    assert summary["remediated"] == 1  # SE-001 changed from FAIL to PASS
    assert summary["maintained_secure"] == 1  # BEN-001 remained PASS
    assert summary["regressions"] == 0
    assert summary["remediation_rate"] == 100.0

    report_content = Path(summary["report_path"]).read_text(encoding="utf-8")
    assert "Remediation & Retest Verification Report" in report_content
    assert "REMEDIATED" in report_content

