"""Tests for the rule-based priority override engine."""

import pytest
from pathlib import Path

from caremap.priority_rules import (
    PriorityRule,
    load_priority_rules,
    apply_priority_rules,
    PRIORITY_RANK,
)


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def sample_rules():
    """A small set of rules for testing."""
    return [
        PriorityRule("edema", "STAT", "Pulmonary Edema Rule", "Immediate intervention"),
        PriorityRule("pneumothorax", "STAT", "Pneumothorax Rule", "Immediate intervention"),
        PriorityRule("consolidation", "SOON", "Consolidation Rule", "Same-day eval"),
        PriorityRule("mass", "SOON", "Mass Rule", "Rule out malignancy"),
        PriorityRule("cardiomegaly", "ROUTINE", "Cardiomegaly Rule", "Chronic finding"),
    ]


# ── CSV Loading ───────────────────────────────────────────────────

class TestLoadPriorityRules:
    def test_loads_default_csv(self):
        rules = load_priority_rules()
        assert len(rules) > 0
        assert all(isinstance(r, PriorityRule) for r in rules)

    def test_all_priorities_valid(self):
        rules = load_priority_rules()
        for rule in rules:
            assert rule.min_priority in PRIORITY_RANK, (
                f"{rule.rule_name} has invalid priority: {rule.min_priority}"
            )

    def test_patterns_are_lowercase(self):
        rules = load_priority_rules()
        for rule in rules:
            assert rule.finding_pattern == rule.finding_pattern.lower()

    def test_has_stat_rules(self):
        rules = load_priority_rules()
        stat_rules = [r for r in rules if r.min_priority == "STAT"]
        assert len(stat_rules) >= 2

    def test_has_soon_rules(self):
        rules = load_priority_rules()
        soon_rules = [r for r in rules if r.min_priority == "SOON"]
        assert len(soon_rules) >= 3


# ── Priority Escalation ──────────────────────────────────────────

class TestApplyPriorityRules:
    def test_edema_escalates_to_stat(self, sample_rules):
        final, reason, matched = apply_priority_rules(
            findings=["Pulmonary edema", "Cardiomegaly"],
            model_priority="SOON",
            rules=sample_rules,
        )
        assert final == "STAT"
        assert reason is not None
        assert "Pulmonary Edema Rule" in reason
        assert "Pulmonary Edema Rule" in matched

    def test_consolidation_escalates_routine_to_soon(self, sample_rules):
        final, reason, matched = apply_priority_rules(
            findings=["Consolidation in right lower lobe"],
            model_priority="ROUTINE",
            rules=sample_rules,
        )
        assert final == "SOON"
        assert reason is not None
        assert "Consolidation Rule" in matched

    def test_model_stat_not_downgraded_by_routine_rule(self, sample_rules):
        final, reason, matched = apply_priority_rules(
            findings=["Cardiomegaly"],
            model_priority="STAT",
            rules=sample_rules,
        )
        assert final == "STAT"
        assert reason is None  # No change

    def test_model_priority_unchanged_when_rules_agree(self, sample_rules):
        final, reason, matched = apply_priority_rules(
            findings=["Consolidation noted"],
            model_priority="SOON",
            rules=sample_rules,
        )
        assert final == "SOON"
        assert reason is None

    def test_no_rules_matched_returns_model_priority(self, sample_rules):
        final, reason, matched = apply_priority_rules(
            findings=["Mild scoliosis"],
            model_priority="ROUTINE",
            rules=sample_rules,
        )
        assert final == "ROUTINE"
        assert reason is None
        assert matched == []

    def test_multiple_rules_highest_wins(self, sample_rules):
        final, reason, matched = apply_priority_rules(
            findings=["Consolidation", "Pulmonary edema"],
            model_priority="ROUTINE",
            rules=sample_rules,
        )
        assert final == "STAT"
        assert "Pulmonary Edema Rule" in matched
        assert "Consolidation Rule" in matched


# ── Case Insensitive ─────────────────────────────────────────────

class TestCaseInsensitive:
    def test_uppercase_finding(self, sample_rules):
        final, _, matched = apply_priority_rules(
            findings=["PULMONARY EDEMA"],
            model_priority="ROUTINE",
            rules=sample_rules,
        )
        assert final == "STAT"
        assert "Pulmonary Edema Rule" in matched

    def test_mixed_case_finding(self, sample_rules):
        final, _, matched = apply_priority_rules(
            findings=["Pulmonary Edema with bilateral infiltrates"],
            model_priority="ROUTINE",
            rules=sample_rules,
        )
        assert final == "STAT"

    def test_mixed_case_model_priority(self, sample_rules):
        final, _, _ = apply_priority_rules(
            findings=["Pulmonary edema"],
            model_priority="soon",
            rules=sample_rules,
        )
        assert final == "STAT"


# ── No Finding → ROUTINE ─────────────────────────────────────────

class TestNoFinding:
    def test_no_finding_forces_routine(self, sample_rules):
        final, reason, _ = apply_priority_rules(
            findings=["No Finding"],
            model_priority="SOON",
            rules=sample_rules,
        )
        assert final == "ROUTINE"
        assert reason is not None
        assert "ROUTINE" in reason

    def test_normal_forces_routine(self, sample_rules):
        final, reason, _ = apply_priority_rules(
            findings=["Normal chest radiograph"],
            model_priority="SOON",
            rules=sample_rules,
        )
        assert final == "ROUTINE"

    def test_unremarkable_forces_routine(self, sample_rules):
        final, reason, _ = apply_priority_rules(
            findings=["Unremarkable study"],
            model_priority="STAT",
            rules=sample_rules,
        )
        assert final == "ROUTINE"

    def test_no_finding_already_routine_no_reason(self, sample_rules):
        final, reason, _ = apply_priority_rules(
            findings=["No Finding"],
            model_priority="ROUTINE",
            rules=sample_rules,
        )
        assert final == "ROUTINE"
        assert reason is None  # Already correct, no override needed


# ── Substring Matching ────────────────────────────────────────────

class TestSubstringMatching:
    def test_infiltrat_matches_infiltrates(self, sample_rules):
        rules_with_infiltrat = sample_rules + [
            PriorityRule("infiltrat", "SOON", "Infiltration Rule", "Same-day eval")
        ]
        final, _, matched = apply_priority_rules(
            findings=["Bilateral infiltrates"],
            model_priority="ROUTINE",
            rules=rules_with_infiltrat,
        )
        assert final == "SOON"
        assert "Infiltration Rule" in matched

    def test_partial_match_pneumothorax(self, sample_rules):
        final, _, matched = apply_priority_rules(
            findings=["Left-sided pneumothorax"],
            model_priority="ROUTINE",
            rules=sample_rules,
        )
        assert final == "STAT"
        assert "Pneumothorax Rule" in matched
