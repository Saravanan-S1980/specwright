"""Typed data that flows between pipeline stages.

Every stage reads and writes these models instead of free text. That's what
makes outputs checkable: an eval can count Problems, verify that every
evidence_id exists, and so on.
"""

from enum import Enum

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    ticket = "ticket"
    interview = "interview"
    sop = "sop"
    idea = "idea"
    transcript = "transcript"


class Evidence(BaseModel):
    """One citable unit of input: a ticket, an interview answer, an SOP step."""

    id: str = Field(description="Stable ID, e.g. 'T-0042'. Citations point here.")
    source_type: SourceType
    text: str = Field(min_length=1)
    title: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Problem(BaseModel):
    """A user problem found in the evidence. Stage 2 output."""

    title: str = Field(description="Short name of the problem, under 12 words")
    description: str = Field(description="What goes wrong and for whom, 1-3 sentences")
    persona: str = Field(description="Who is affected, e.g. 'patient booking for a parent'")
    severity: Severity
    evidence_ids: list[str] = Field(
        min_length=1, description="IDs of the Evidence items that show this problem"
    )

    @property
    def frequency(self) -> int:
        return len(self.evidence_ids)


class ProblemList(BaseModel):
    problems: list[Problem]
