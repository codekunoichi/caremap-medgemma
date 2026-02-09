"""
Rule-based priority override for radiology triage.

MedGemma detects findings; this physician-auditable rule engine
assigns priority based on clinical significance of findings.
Rules only escalate priority — they never downgrade, except for
the special "No Finding" case which forces ROUTINE.
"""

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


PRIORITY_RANK = {"ROUTINE": 1, "SOON": 2, "STAT": 3}
RANK_TO_PRIORITY = {v: k for k, v in PRIORITY_RANK.items()}

_NO_FINDING_TERMS = {"no finding", "normal", "unremarkable"}

_cached_rules: Optional[list] = None


@dataclass
class PriorityRule:
    """A single clinical priority rule."""
    finding_pattern: str
    min_priority: str
    rule_name: str
    clinical_rationale: str


def load_priority_rules(rules_path: Optional[str] = None) -> list[PriorityRule]:
    """Load priority rules from a CSV file.

    Args:
        rules_path: Path to CSV. Defaults to data/nih_chest_xray/radiology_priority_rules.csv.

    Returns:
        List of PriorityRule objects.
    """
    if rules_path is None:
        rules_path = (
            Path(__file__).parent.parent.parent
            / "data" / "nih_chest_xray" / "radiology_priority_rules.csv"
        )
    else:
        rules_path = Path(rules_path)

    rules = []
    with open(rules_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rules.append(PriorityRule(
                finding_pattern=row["finding_pattern"].strip().lower(),
                min_priority=row["min_priority"].strip().upper(),
                rule_name=row["rule_name"].strip(),
                clinical_rationale=row["clinical_rationale"].strip(),
            ))
    return rules


def get_default_rules() -> list[PriorityRule]:
    """Return cached default rules (loaded once per process)."""
    global _cached_rules
    if _cached_rules is None:
        _cached_rules = load_priority_rules()
    return _cached_rules


def apply_priority_rules(
    findings: list[str],
    model_priority: str,
    rules: list[PriorityRule],
) -> tuple[str, Optional[str], list[str]]:
    """Apply rule-based priority override to MedGemma findings.

    Rules only escalate — final priority is max(model, matched rules).
    Special case: "No Finding" / "Normal" / "Unremarkable" forces ROUTINE.

    Args:
        findings: List of finding strings from MedGemma.
        model_priority: Priority assigned by MedGemma (STAT/SOON/ROUTINE).
        rules: List of PriorityRule to apply.

    Returns:
        (final_priority, override_reason, matched_rule_names)
        override_reason is None if priority unchanged.
    """
    model_priority = model_priority.upper()
    findings_lower = [f.lower() for f in findings]

    # Special case: no findings → force ROUTINE
    for finding in findings_lower:
        if any(term in finding for term in _NO_FINDING_TERMS):
            matched = []
            if model_priority != "ROUTINE":
                reason = f"Rule override: '{finding}' indicates normal study → ROUTINE"
                return "ROUTINE", reason, matched
            return "ROUTINE", None, matched

    # Match rules against findings
    matched_rules: list[PriorityRule] = []
    for rule in rules:
        for finding in findings_lower:
            if rule.finding_pattern in finding:
                matched_rules.append(rule)
                break  # Each rule matches at most once

    matched_rule_names = [r.rule_name for r in matched_rules]

    if not matched_rules:
        return model_priority, None, matched_rule_names

    # Find highest priority from matched rules
    max_rule_rank = max(PRIORITY_RANK.get(r.min_priority, 1) for r in matched_rules)
    model_rank = PRIORITY_RANK.get(model_priority, 1)

    final_rank = max(model_rank, max_rule_rank)
    final_priority = RANK_TO_PRIORITY[final_rank]

    override_reason = None
    if final_priority != model_priority:
        triggering = [r for r in matched_rules if PRIORITY_RANK[r.min_priority] == max_rule_rank]
        override_reason = (
            f"Rule override: {triggering[0].rule_name} "
            f"({model_priority} → {final_priority})"
        )

    return final_priority, override_reason, matched_rule_names
