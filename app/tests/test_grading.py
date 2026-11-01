import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from grading import grade, at_risk_reasons


def test_grade_boundaries():
    assert grade(95) == "A+" and grade(90) == "A+" and grade(89.9) == "A"
    assert grade(70) == "B" and grade(50) == "D" and grade(49.9) == "F"


def test_at_risk_subject_and_overall():
    assert at_risk_reasons({"Maths": 35, "Sci": 90}, 62.5)
    assert at_risk_reasons({"Maths": 45, "Sci": 48}, 46.5)
    assert not at_risk_reasons({"Maths": 75, "Sci": 80}, 77.5)
