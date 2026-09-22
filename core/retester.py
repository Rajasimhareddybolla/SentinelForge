import json
import ast
import requests
from pathlib import Path
from typing import Dict, Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_REPORTS_DIR = _PROJECT_ROOT / "reports"

class Retester:
    def __init__(self, target_uri: str = "http://127.0.0.1:8000/chat"):
        self.target_uri = target_uri

    def _extract_raw_prompt(self, prompt_str: str) -> str:
        """Attempt to extract the actual text payload from tool-specific prompt formats."""
        try:
            # Garak often stores stringified python dicts
            data = ast.literal_eval(prompt_str)
            if isinstance(data, dict) and "turns" in data:
                turns = data["turns"]
                if turns and "content" in turns[-1]:
                    return turns[-1]["content"].get("text", prompt_str)
        except (ValueError, SyntaxError):
            pass
        return prompt_str

    def retest_finding(self, finding_id: str) -> None:
        findings_path = _REPORTS_DIR / "unified_findings.json"
        if not findings_path.exists():
            print(f"[ERROR] Findings database not found at {findings_path}")
            return
            
        with open(findings_path, "r") as f:
            findings = json.load(f)
            
        target_finding = next((f for f in findings if f["finding_id"] == finding_id), None)
        if not target_finding:
            print(f"[ERROR] Finding ID {finding_id} not found in database.")
            return
            
        print(f"================================================================================")
        print(f"  RETESTING FINDING: {finding_id} - {target_finding['category']}")
        print(f"================================================================================")
        
        # Test up to 3 instances
        instances = target_finding.get("instances", [])[:3]
        
        for idx, instance in enumerate(instances):
            raw_prompt = self._extract_raw_prompt(instance.get("prompt", ""))
            original_response = instance.get("response", "")
            
            print(f"\n--- [ Instance {idx+1} ({instance.get('module_or_probe', 'unknown')}) ] ---")
            print(f"[ATTACK PROMPT]\n{raw_prompt}")
            
            try:
                resp = requests.post(
                    self.target_uri, 
                    json={"message": raw_prompt},
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                if resp.status_code == 200:
                    new_response = resp.json().get("response", str(resp.text))
                else:
                    new_response = f"HTTP {resp.status_code}: {resp.text}"
            except Exception as e:
                new_response = f"Connection Error: {e}"
                
            print(f"\n[ORIGINAL VULNERABLE RESPONSE]\n{original_response}")
            print(f"\n[NEW DEFENDED RESPONSE]\n{new_response}")
            print("-" * 80)

