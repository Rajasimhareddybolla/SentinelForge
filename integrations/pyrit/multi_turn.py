"""Multi-turn adversarial attack orchestrator using Microsoft PyRIT paradigms.

Executes sequential, stateful conversational campaigns (such as Crescendo context drift,
IT Helpdesk persona escalation, and commercial policy bypasses) against the Northwind target,
evaluating security boundaries turn-by-turn with deterministic scoring.
"""

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid
import yaml

from pyrit.models import Message, MessagePiece

from engine.scorers.composite_scorer import CompositeScorer
from integrations.pyrit.target_adapter import NorthwindPyritTarget

logger = logging.getLogger("sentinelforge.pyrit.multi_turn")


@dataclass
class CampaignTurn:
    turn_index: int
    technique: str
    prompt: str
    expected_safe: bool = True


@dataclass
class MultiTurnCampaign:
    campaign_id: str
    name: str
    category: str
    severity: str
    description: str
    invariants_tested: List[str]
    turns: List[CampaignTurn]

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "MultiTurnCampaign":
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        turns = [
            CampaignTurn(
                turn_index=t.get("turn_index", i + 1),
                technique=t.get("technique", "Unknown Technique"),
                prompt=t.get("prompt", "").strip(),
                expected_safe=t.get("expected_safe", True),
            )
            for i, t in enumerate(data.get("turns", []))
        ]

        return cls(
            campaign_id=data.get("campaign_id", "MT-GENERIC"),
            name=data.get("name", "Unnamed Multi-Turn Campaign"),
            category=data.get("category", "Multi-Turn Dialogue"),
            severity=data.get("severity", "medium"),
            description=data.get("description", "").strip(),
            invariants_tested=data.get("invariants_tested", []),
            turns=turns,
        )


def load_all_campaigns(campaigns_dir: Optional[Path] = None) -> List[MultiTurnCampaign]:
    """Loads all multi-turn campaign definitions from the attack datasets directory."""
    if campaigns_dir is None:
        project_root = Path(__file__).resolve().parent.parent.parent
        campaigns_dir = project_root / "datasets" / "attacks" / "multi_turn"

    campaign_files = sorted(campaigns_dir.glob("*.yaml")) + sorted(campaigns_dir.glob("*.yml"))
    campaigns = []
    for cf in campaign_files:
        try:
            campaigns.append(MultiTurnCampaign.from_yaml(cf))
        except Exception as exc:
            logger.error("Failed to load campaign file %s: %s", cf, exc)

    return campaigns


class MultiTurnOrchestrator:
    """Runs stateful multi-turn PyRIT attack campaigns against Northwind target."""

    def __init__(
        self,
        pyrit_target: NorthwindPyritTarget,
        scorer: Optional[CompositeScorer] = None,
    ):
        self.pyrit_target = pyrit_target
        self.scorer = scorer or CompositeScorer()

    async def run_campaign(self, campaign: MultiTurnCampaign) -> Dict[str, Any]:
        """Executes a single multi-turn campaign turn by turn with session preservation."""
        session_id = f"pyrit-{campaign.campaign_id.lower()}-{uuid.uuid4().hex[:6]}"
        self.pyrit_target.session_id = session_id

        turn_results = []
        is_compromised = False
        earliest_turn_compromised = None

        logger.info(
            "Starting multi-turn campaign '%s' [%d turns, session=%s]",
            campaign.name,
            len(campaign.turns),
            session_id,
        )

        for turn in campaign.turns:
            msg = Message(
                message_pieces=[
                    MessagePiece(
                        role="user",
                        original_value=turn.prompt,
                        conversation_id=session_id,
                    )
                ]
            )

            # Send prompt to Northwind via PyRIT target adapter
            response_messages = await self.pyrit_target.send_prompt_async(message=msg)
            resp_piece = response_messages[0].get_piece()
            response_text = resp_piece.original_value or resp_piece.converted_value

            # Evaluate response using deterministic CompositeScorer
            test_case_meta = {
                "id": f"{campaign.campaign_id}-T{turn.turn_index}",
                "expected": {
                    "secret_leaked": False,
                    "prompt_leaked": False,
                },
            }
            score_res = self.scorer.evaluate(response_text, test_case_meta)

            turn_leaked = score_res.secret_detected or score_res.prompt_leak_detected
            if turn_leaked and not is_compromised:
                is_compromised = True
                earliest_turn_compromised = turn.turn_index

            turn_results.append({
                "turn_index": turn.turn_index,
                "technique": turn.technique,
                "user_prompt": turn.prompt,
                "response": response_text,
                "score_passed": score_res.passed,
                "secret_detected": score_res.secret_detected,
                "prompt_leak_detected": score_res.prompt_leak_detected,
                "violations": score_res.violations,
                "score_summary": score_res.summary,
                "telemetry": self.pyrit_target.last_telemetry,
                "latency_ms": self.pyrit_target.last_latency_ms,
            })

            logger.info(
                "Turn %d/%d [%s] => %s",
                turn.turn_index,
                len(campaign.turns),
                turn.technique,
                "FAIL (Leaked Invariant)" if turn_leaked else "PASS (Protected)",
            )

        return {
            "campaign_id": campaign.campaign_id,
            "name": campaign.name,
            "category": campaign.category,
            "severity": campaign.severity,
            "description": campaign.description,
            "invariants_tested": campaign.invariants_tested,
            "session_id": session_id,
            "turns_executed": len(campaign.turns),
            "compromised": is_compromised,
            "earliest_turn_compromised": earliest_turn_compromised,
            "turns": turn_results,
            "summary": (
                f"Campaign COMPROMISED at Turn {earliest_turn_compromised}"
                if is_compromised
                else "Campaign CONTAINED (All turns successfully defended)"
            ),
        }
