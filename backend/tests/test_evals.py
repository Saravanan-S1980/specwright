"""Tests for the eval scorer. No API key needed: score() is a pure function."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "evals"))

from run_evals import score, usage_and_cost  # noqa: E402

from app.schemas import Problem, Severity  # noqa: E402


def prob(ids: list[str]) -> Problem:
    return Problem(title="t", description="d", persona="p", severity=Severity.high, evidence_ids=ids)


PLANTED = [
    {"id": "P1", "title": "Big", "ticket_ids": [f"A{i}" for i in range(10)]},
    {"id": "P2", "title": "Small", "ticket_ids": [f"B{i}" for i in range(4)]},
]


def test_found_needs_one_problem_with_half_the_tickets():
    s = score([prob([f"A{i}" for i in range(5)])], PLANTED)
    assert s["found"] == 1 and s["covered"] == 1


def test_split_problem_is_covered_but_not_found():
    # 3 + 3 of 10 tickets: no single piece reaches 50%, together they hit 60%.
    s = score([prob(["A0", "A1", "A2"]), prob(["A3", "A4", "A5"])], PLANTED)
    p1 = s["problems"][0]
    assert not p1["found"] and p1["covered"]
    assert p1["split_into"] == [1, 2]
    assert s["found"] == 0 and s["covered"] == 1


def test_single_stray_ticket_is_not_a_split():
    s = score([prob([f"A{i}" for i in range(6)]), prob(["A9"])], PLANTED)
    assert s["problems"][0]["split_into"] == []


def test_noise_tickets_are_counted_once():
    s = score([prob(["A0", "N1", "N2"]), prob(["N2", "B0"])], PLANTED)
    assert s["noise_tickets_cited"] == ["N1", "N2"]


def test_rank_order_detects_swap():
    # Expected: P1 first, P2 second. Returned in the opposite order.
    s = score([prob(["B0", "B1"]), prob([f"A{i}" for i in range(6)])], PLANTED)
    assert s["found"] == 2 and not s["rank_order_matches"]


def test_empty_result_scores_zero():
    s = score([], PLANTED)
    assert s["found"] == 0 and s["covered"] == 0


def test_cost_uses_price_table():
    calls = [{"model": "claude-sonnet-5-5", "input_tokens": 1_000_000, "output_tokens": 100_000}]
    assert usage_and_cost(calls)["cost_usd"] == 3.0  # $2 in + $1 out
