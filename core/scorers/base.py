"""Base classes and data models for security scorers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ScoreResult:
    """Represents the evaluation verdict of a security test."""
    passed: bool
    violations: List[str] = field(default_factory=list)
    secret_detected: bool = False
    prompt_leak_detected: bool = False
    details: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""

    @property
    def is_vulnerable(self) -> bool:
        return not self.passed


class BaseScorer(ABC):
    """Abstract base class for all SentinelForge security scorers."""

    @abstractmethod
    def evaluate(self, response_text: str, test_case: Dict[str, Any]) -> ScoreResult:
        """Evaluate LLM response text against security criteria and return ScoreResult."""
        pass

