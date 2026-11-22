from pathlib import Path

import pytest

from app.ingest.tickets import TicketParseError, parse_tickets_csv
from app.schemas import SourceType

DATASET = Path(__file__).parents[2] / "evals/datasets/clinic_tickets_v1/tickets.csv"


def test_parses_golden_dataset():
    evidence = parse_tickets_csv(DATASET.read_text(encoding="utf-8"))
    assert len(evidence) == 200
    first = evidence[0]
    assert first.id.startswith("T-")
    assert first.source_type is SourceType.ticket
    assert first.title
    assert "channel" in first.metadata


def test_accepts_column_aliases():
    raw = "Case_ID,Description,Summary\n7,App crashed on login,Crash\n"
    [e] = parse_tickets_csv(raw)
    assert (e.id, e.text, e.title) == ("7", "App crashed on login", "Crash")


def test_skips_empty_bodies():
    raw = "id,body\n1,Real problem\n2,\n"
    assert [e.id for e in parse_tickets_csv(raw)] == ["1"]


def test_rejects_csv_without_body_column():
    with pytest.raises(TicketParseError, match="body column"):
        parse_tickets_csv("id,priority\n1,high\n")
