import os

SUBJECT_MIN = float(os.getenv("AT_RISK_SUBJECT", "40"))   # below this in any subject -> at risk
OVERALL_MIN = float(os.getenv("AT_RISK_OVERALL", "50"))   # below this overall -> at risk


def grade(pct: float) -> str:
    for cutoff, g in ((90, "A+"), (80, "A"), (70, "B"), (60, "C"), (50, "D")):
        if pct >= cutoff:
            return g
    return "F"


def at_risk_reasons(subject_avgs: dict, overall: float,
                    subject_min: float = SUBJECT_MIN, overall_min: float = OVERALL_MIN) -> list:
    reasons = [f"{n}: {v:.0f}% (below {subject_min:.0f}%)"
               for n, v in subject_avgs.items() if v < subject_min]
    if subject_avgs and overall < overall_min:
        reasons.append(f"Overall {overall:.0f}% (below {overall_min:.0f}%)")
    return reasons
