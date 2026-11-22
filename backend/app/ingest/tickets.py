"""Parse a support-ticket CSV export into Evidence.

Help desks name their columns differently, so we accept a few common aliases.
Only an ID column and a body column are required.
"""

import csv
import io

from app.schemas import Evidence, SourceType

ID_ALIASES = ("ticket_id", "id", "ticket", "case_id", "number")
BODY_ALIASES = ("body", "description", "message", "text", "content")
TITLE_ALIASES = ("subject", "title", "summary")


class TicketParseError(ValueError):
    pass


def _find(headers: list[str], aliases: tuple[str, ...]) -> str | None:
    lowered = {h.strip().lower(): h for h in headers}
    for alias in aliases:
        if alias in lowered:
            return lowered[alias]
    return None


def parse_tickets_csv(raw: str) -> list[Evidence]:
    reader = csv.DictReader(io.StringIO(raw))
    headers = reader.fieldnames or []

    id_col = _find(headers, ID_ALIASES)
    body_col = _find(headers, BODY_ALIASES)
    title_col = _find(headers, TITLE_ALIASES)
    if not id_col or not body_col:
        raise TicketParseError(
            f"CSV needs an ID column ({', '.join(ID_ALIASES)}) and a body column "
            f"({', '.join(BODY_ALIASES)}). Found: {', '.join(headers) or 'none'}"
        )

    used = {id_col, body_col, title_col}
    evidence: list[Evidence] = []
    for row in reader:
        body = (row.get(body_col) or "").strip()
        if not body:
            continue  # empty tickets carry no evidence
        evidence.append(
            Evidence(
                id=row[id_col].strip(),
                source_type=SourceType.ticket,
                text=body,
                title=(row.get(title_col) or "").strip() or None if title_col else None,
                # keep every other column (priority, channel, date) as metadata
                metadata={k: v for k, v in row.items() if k not in used and v},
            )
        )
    return evidence
