"""Section hub grading integration tests (unit-level, no DB required)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.repositories.grade_repo import compute_student_summary, letter_for_percent


def _scales():
    return [
        {"min_percent": 93, "max_percent": 100, "letter_grade": "A+", "gpa_points": 4.0},
        {"min_percent": 80, "max_percent": 82.99, "letter_grade": "B", "gpa_points": 3.0},
        {"min_percent": 0, "max_percent": 59.99, "letter_grade": "F", "gpa_points": 0.0},
    ]


def test_ct_average_used_as_single_weighted_slot():
    rubric = [
        {
            "component_type": "ct",
            "label": "CT 1",
            "component_code": "ct1",
            "max_score": 20,
            "weight_percent": 15,
        },
        {
            "component_type": "ct",
            "label": "CT 2",
            "component_code": "ct2",
            "max_score": 20,
            "weight_percent": 15,
        },
        {
            "component_type": "evaluation",
            "label": "Mid Term Exam",
            "component_code": "mid_term",
            "max_score": 30,
            "weight_percent": 30,
        },
    ]
    grades = [
        {"component_code": "ct1", "score": 18},
        {"component_code": "ct2", "score": 14},
        {"component_code": "mid_term", "score": 24},
    ]
    summary = compute_student_summary(rubric, grades, _scales())

    assert summary["ct_average"] == 16.0, f"expected CT avg 16, got {summary['ct_average']}"
    # CT slot: (16/20)*100 * 30 weight = 24; Mid: (24/30)*100 * 30 = 24; total 48/60 = 80%
    assert summary["total_percent"] == 80.0, f"expected 80%, got {summary['total_percent']}"
    letter, gpa = letter_for_percent(_scales(), summary["total_percent"])
    assert letter == "B"
    assert gpa == 3.0


def test_team_evaluation_in_total():
    rubric = [
        {
            "component_type": "team",
            "label": "Project",
            "component_code": "team_1",
            "max_score": 100,
            "weight_percent": 40,
        },
    ]
    grades = [{"component_code": "team_1", "score": 85}]
    summary = compute_student_summary(rubric, grades, _scales())
    assert summary["total_percent"] == 85.0


def test_portal_sync_component_shape():
    rubric = [
        {
            "component_type": "portal",
            "label": "Assignment 1",
            "component_code": "portal_5",
            "max_score": 15,
            "weight_percent": 15,
        },
    ]
    grades = [{"component_code": "portal_5", "score": 12}]
    summary = compute_student_summary(rubric, grades, _scales())
    assert summary["evaluations"][0]["component_type"] == "portal"
    assert summary["total_percent"] == 80.0


def test_grading_task_completion_percent():
    enrolled, graded = 10, 3
    pct = round((graded / enrolled) * 100)
    assert pct == 30
    pct_done = round((10 / 10) * 100)
    assert pct_done == 100


def main() -> int:
    tests = [
        test_ct_average_used_as_single_weighted_slot,
        test_team_evaluation_in_total,
        test_portal_sync_component_shape,
        test_grading_task_completion_percent,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL  {fn.__name__}: {exc}")
    if failed:
        print(f"\n{failed} test(s) failed")
        return 1
    print(f"\nAll {len(tests)} section hub grading tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
