"""Unit tests for SentinelForge orchestrator, datasets, and evidence collector."""

import json
from pathlib import Path
import pytest
from app.northwind.client import GroqClient
from app.northwind.config import get_settings
from core.evidence.collector import EvidenceCollector
from core.orchestrator.runner import AssessmentRunner
from core.orchestrator.target import DirectTarget
from core.scorers.base import ScoreResult


def test_load_attacks():
    runner = AssessmentRunner()
    attacks = runner.load_attacks()
    assert len(attacks) >= 15, "Expected at least 15 attack scenarios"
    
    # Verify mandatory fields in all attack definitions
    for attack in attacks:
        assert "id" in attack, f"Missing 'id' in attack: {attack}"
        assert "category" in attack, f"Missing 'category' in attack: {attack}"
        assert "prompt" in attack, f"Missing 'prompt' in attack: {attack}"
        assert "expected" in attack, f"Missing 'expected' in attack: {attack}"


def test_evidence_collector(tmp_path):
    collector = EvidenceCollector(output_dir=tmp_path)
    test_case = {
        "id": "TEST-001",
        "name": "Test Injection Scenario",
        "category": "prompt-injection",
        "severity": "CRITICAL",
        "owasp_category": "LLM01: Prompt Injection",
    }
    score_result = ScoreResult(
        passed=False,
        violations=["Secret disclosure detected"],
        secret_detected=True,
        prompt_leak_detected=False,
        details={"test": "ok"},
    )

    evidence = collector.record_evidence(
        test_case=test_case,
        prompt="Adversarial input payload",
        response_text="Leaked key NORTHWIND_TEST_KEY_12345",
        score_result=score_result,
        model_name="mock-model",
        latency_ms=12.5,
    )

    assert evidence["test_id"] == "TEST-001"
    assert evidence["result"] == "FAIL"
    assert evidence["secret_detected"] is True

    # Verify file written to disk
    saved_file = tmp_path / "TEST-001.json"
    assert saved_file.exists()
    with open(saved_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["test_id"] == "TEST-001"
    assert data["reproduction_command"] == "python reproduce.py TEST-001"


@pytest.mark.asyncio
async def test_assessment_runner_mock_run(tmp_path):
    settings = get_settings()
    original_mock = settings.mock_mode
    settings.mock_mode = True

    try:
        mock_client = GroqClient(settings=settings)
        target = DirectTarget(groq_client=mock_client)
        
        runner = AssessmentRunner(
            target=target,
            results_dir=tmp_path,
            pacing_delay_sec=0.0,
        )

        summary = await runner.run_assessment()
        assert summary["total"] >= 15
        assert summary["passed"] + summary["failed"] == summary["total"]
        assert Path(summary["report_path"]).exists()

        # Verify report contains key headers
        report_content = Path(summary["report_path"]).read_text(encoding="utf-8")
        assert "SentinelForge — AI Security Assessment Report" in report_content
        assert "Executive Summary" in report_content
        assert "Category Breakdown" in report_content

    finally:
        settings.mock_mode = original_mock

