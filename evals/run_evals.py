"""Eval v0: can the synthesize stage find the 8 problems planted in 200 tickets?

Run from the repo root:  python evals/run_evals.py
It calls the real model, so it needs SPECWRIGHT_API_KEY and costs a few cents.

Two scores, because they answer different questions:
- found:   one returned problem matches a planted problem on its own (strict).
- covered: the returned problems together cite at least half of the planted
           tickets, even if Claude split the problem into several pieces (lenient).
A big gap between the two means Claude finds the right problems but slices
them too thin.
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app import llm  # noqa: E402
from app.config import settings  # noqa: E402
from app.ingest.tickets import parse_tickets_csv  # noqa: E402
from app.schemas import Problem  # noqa: E402
from app.stages.synthesize import PROMPT_VERSION, synthesize  # noqa: E402

DATASET = ROOT / "evals" / "datasets" / "clinic_tickets_v1"
RESULTS_DIR = ROOT / "evals" / "results"

THRESHOLD = 0.5  # share of a planted problem's tickets that must be matched
# A returned problem counts as "a piece" of a planted problem when it cites at
# least this many of its tickets. Two keeps one stray ticket from looking like a split.
MIN_PIECE_TICKETS = 2

# USD per million tokens (input, output). Session 4 moves this into config.py
# and into the traces; until then the eval keeps its own copy.
PRICES = {
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-opus-5-5": (4.00, 20.00),
}


def score(problems: list[Problem], planted: list[dict]) -> dict:
    """Compare returned problems to planted ones. Pure function, no API calls."""
    planted_ids = {t for p in planted for t in p["ticket_ids"]}
    rows = []
    for p in planted:
        truth = set(p["ticket_ids"])
        # Overlap of each returned problem with this planted problem's tickets.
        overlaps = [len(truth & set(r.evidence_ids)) for r in problems]

        # found: the single best returned problem hits >= 50% of the tickets.
        best = max(range(len(problems)), key=lambda i: overlaps[i], default=None)
        best_share = overlaps[best] / len(truth) if best is not None else 0.0

        # covered: the union across all returned problems hits >= 50%.
        union = set().union(*(truth & set(r.evidence_ids) for r in problems)) if problems else set()
        covered_share = len(union) / len(truth)

        pieces = [i for i, n in enumerate(overlaps) if n >= MIN_PIECE_TICKETS]
        rows.append({
            "id": p["id"],
            "title": p["title"],
            "expected_rank": None,  # filled below
            "expected_count": len(truth),
            "found": best_share >= THRESHOLD,
            "best_share": round(best_share, 3),
            "matched_rank": best + 1 if best_share >= THRESHOLD else None,
            "covered": covered_share >= THRESHOLD,
            "covered_share": round(covered_share, 3),
            "split_into": [i + 1 for i in pieces] if len(pieces) > 1 else [],
        })

    # Expected order is by ticket count, biggest first (ties keep file order).
    for rank, row in enumerate(sorted(rows, key=lambda r: -r["expected_count"]), start=1):
        row["expected_rank"] = rank

    # Rank order: do the found problems appear in the expected order?
    found_rows = sorted((r for r in rows if r["found"]), key=lambda r: r["expected_rank"])
    matched = [r["matched_rank"] for r in found_rows]
    in_order = matched == sorted(matched)

    # Noise: tickets cited by any returned problem that belong to no planted problem.
    cited = {t for r in problems for t in r.evidence_ids}
    noise_cited = sorted(cited - planted_ids)

    return {
        "found": sum(r["found"] for r in rows),
        "covered": sum(r["covered"] for r in rows),
        "total_planted": len(rows),
        "rank_order_matches": in_order,
        "noise_tickets_cited": noise_cited,
        "problems": rows,
    }


def read_trace_since(offset: int) -> list[dict]:
    """Read the trace lines llm.py wrote during this run (everything after `offset`)."""
    path = llm.TRACE_PATH
    if not path.exists():
        return []
    with path.open("rb") as f:
        f.seek(offset)
        lines = f.read().decode("utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def usage_and_cost(calls: list[dict]) -> dict:
    tokens_in = sum(c["input_tokens"] for c in calls)
    tokens_out = sum(c["output_tokens"] for c in calls)
    cost = 0.0
    for c in calls:
        price_in, price_out = PRICES.get(c["model"], (0.0, 0.0))
        cost += c["input_tokens"] / 1e6 * price_in + c["output_tokens"] / 1e6 * price_out
    return {"api_calls": len(calls), "input_tokens": tokens_in,
            "output_tokens": tokens_out, "cost_usd": round(cost, 4)}


def render(result: dict, planted: list[dict]) -> str:
    s = result["score"]
    n = s["total_planted"]
    lines = [
        f"# Eval report: {result['prompt_version']} on {result['dataset']}",
        "",
        f"- Model: {result['model']}",
        f"- Run at: {result['timestamp']}",
        f"- **Found: {s['found']} of {n}** (one problem matches 50%+ of the tickets)",
        f"- **Covered: {s['covered']} of {n}** (all problems together cite 50%+ of the tickets)",
        f"- Returned problems: {result['returned_problems']}",
        f"- Noise tickets wrongly cited: {len(s['noise_tickets_cited'])} of "
        f"{result['noise_total']} ({', '.join(s['noise_tickets_cited'][:10]) or 'none'}"
        f"{'...' if len(s['noise_tickets_cited']) > 10 else ''})",
        f"- Found problems in expected rank order: {'yes' if s['rank_order_matches'] else 'no'}",
        f"- Tokens: {result['usage']['input_tokens']:,} in, {result['usage']['output_tokens']:,} out "
        f"over {result['usage']['api_calls']} call(s)",
        f"- Cost: ${result['usage']['cost_usd']:.4f}",
        f"- Latency: {result['latency_s']:.1f}s",
        "",
        "| Planted | Tickets | Expected rank | Returned rank | Found | Best match | Covered | Union |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in s["problems"]:
        lines.append(
            f"| {r['id']} {r['title']} | {r['expected_count']} | {r['expected_rank']} | "
            f"{r['matched_rank'] or '-'} | {'yes' if r['found'] else 'no'} | "
            f"{r['best_share']:.0%} | {'yes' if r['covered'] else 'no'} | {r['covered_share']:.0%} |"
        )
    splits = [r for r in s["problems"] if r["split_into"]]
    lines += ["", "## Split across several returned problems", ""]
    if splits:
        for r in splits:
            lines.append(f"- {r['id']} {r['title']}: returned problems "
                         f"{', '.join('#' + str(i) for i in r['split_into'])}")
    else:
        lines.append("None.")
    lines += ["", "## Returned problems", ""]
    for i, p in enumerate(result["problems"], start=1):
        lines.append(f"{i}. {p['title']} ({len(p['evidence_ids'])} tickets, {p['severity']})")
    return "\n".join(lines) + "\n"


def main() -> None:
    if not settings.api_key:
        sys.exit("Set SPECWRIGHT_API_KEY first. This eval calls the real model.")

    truth = json.loads((DATASET / "planted_problems.json").read_text(encoding="utf-8"))
    evidence = parse_tickets_csv((DATASET / "tickets.csv").read_text(encoding="utf-8-sig"))
    print(f"Loaded {len(evidence)} tickets. Calling {settings.model_main}...")

    offset = llm.TRACE_PATH.stat().st_size if llm.TRACE_PATH.exists() else 0
    start = time.perf_counter()
    problems = synthesize(evidence).problems
    latency = time.perf_counter() - start

    result = {
        "dataset": truth["dataset"],
        "prompt_version": PROMPT_VERSION,
        "model": settings.model_main,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ"),
        "returned_problems": len(problems),
        "noise_total": truth["noise_tickets"],
        "latency_s": round(latency, 1),
        "usage": usage_and_cost(read_trace_since(offset)),
        "score": score(problems, truth["problems"]),
        "problems": [p.model_dump(mode="json") for p in problems],
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    stem = RESULTS_DIR / f"{result['timestamp']}_{PROMPT_VERSION}"
    stem.with_suffix(".json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    report = render(result, truth["problems"])
    stem.with_suffix(".md").write_text(report, encoding="utf-8")
    print(report)
    print(f"Saved to {stem}.json and .md")


if __name__ == "__main__":
    main()
