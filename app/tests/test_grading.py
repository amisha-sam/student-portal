import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from grading import grade, at_risk_reasons


def test_grade_boundaries():
    # A+: >= 90
    assert grade(100) == "A+"
    assert grade(95) == "A+"
    assert grade(90) == "A+"
    # A: 80 - 89.9
    assert grade(89.9) == "A"
    assert grade(85) == "A"
    assert grade(80) == "A"
    # B: 70 - 79.9
    assert grade(79.9) == "B"
    assert grade(75) == "B"
    assert grade(70) == "B"
    # C: 60 - 69.9
    assert grade(69.9) == "C"
    assert grade(65) == "C"
    assert grade(60) == "C"
    # D: 50 - 59.9
    assert grade(59.9) == "D"
    assert grade(55) == "D"
    assert grade(50) == "D"
    # F: < 50
    assert grade(49.9) == "F"
    assert grade(30) == "F"
    assert grade(0) == "F"


def test_at_risk_subject_and_overall():
    # Single subject below 40 -> at risk even if overall high
    reasons = at_risk_reasons({"Maths": 35, "Sci": 90}, 62.5)
    assert len(reasons) == 1
    assert "Maths: 35%" in reasons[0]

    # Overall below 50 -> at risk even if all individual subjects >= 40
    reasons_overall = at_risk_reasons({"Maths": 45, "Sci": 48}, 46.5)
    assert any("Overall 46%" in r or "Overall 47%" in r for r in reasons_overall)

    # Both conditions triggered
    reasons_both = at_risk_reasons({"Maths": 35, "Sci": 45}, 40.0)
    assert len(reasons_both) == 2

    # Clean student -> no reasons
    assert not at_risk_reasons({"Maths": 75, "Sci": 80}, 77.5)
    assert not at_risk_reasons({"Maths": 40, "Sci": 60}, 50.0)


def test_custom_thresholds():
    # Test configurable thresholds via arguments
    custom_reasons = at_risk_reasons({"Maths": 45, "Sci": 55}, 50.0, subject_min=50.0, overall_min=60.0)
    assert len(custom_reasons) == 2
