"""Stage 2: synthesize. Turn a pile of Evidence into a ranked ProblemList.

Claude does the grouping, which needs judgment. Our code does everything that
must be exact: formatting the input safely, checking citations, and ranking.
See docs/decisions/0004-rank-and-check-citations-in-code.md.
"""

from html import escape
from pathlib import Path

from app.config import settings
from app.llm import call_structured
from app.schemas import Evidence, Problem, ProblemList, Severity

# Bump the version in the filename when the prompt changes, so eval results
# can say which prompt produced them.
PROMPT_VERSION = "synthesize_v1"
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / f"{PROMPT_VERSION}.md"

# Higher number ranks first when two problems have the same frequency.
SEVERITY_RANK = {
    Severity.critical: 3,
    Severity.high: 2,
    Severity.medium: 1,
    Severity.low: 0,
}


def load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def format_evidence(evidence: list[Evidence]) -> str:
    """Wrap each ticket in <ticket id="..."> tags.

    Why escape? A ticket could contain the text "</ticket>" and then write
    things that look like they sit outside the ticket. Escaping turns < and >
    into &lt; and &gt;, so customer text can never close our tag.
    """
    blocks = []
    for item in evidence:
        text = escape(item.text)
        if item.title:
            text = f"Subject: {escape(item.title)}\n{text}"
        blocks.append(f'<ticket id="{escape(item.id, quote=True)}">\n{text}\n</ticket>')
    return "\n\n".join(blocks)


def clean_citations(problems: list[Problem], known_ids: set[str]) -> list[Problem]:
    """Drop evidence IDs Claude made up, and problems left with no evidence.

    Every output has to trace back to real evidence. A made-up ID would break
    that promise silently, so we remove it here instead of trusting the model.
    """
    cleaned = []
    for problem in problems:
        # dict.fromkeys removes duplicates and keeps the original order
        ids = [i for i in dict.fromkeys(problem.evidence_ids) if i in known_ids]
        if ids:
            cleaned.append(problem.model_copy(update={"evidence_ids": ids}))
    return cleaned


def rank(problems: list[Problem]) -> list[Problem]:
    """Most tickets first. Ties go to the more severe problem."""
    return sorted(
        problems,
        key=lambda p: (p.frequency, SEVERITY_RANK[p.severity]),
        reverse=True,
    )


def synthesize(evidence: list[Evidence]) -> ProblemList:
    """Find the user problems in `evidence` and return them ranked."""
    if not evidence:
        return ProblemList(problems=[])

    result = call_structured(
        model=settings.model_main,
        system=load_prompt(),
        user=format_evidence(evidence),
        output_model=ProblemList,
    )
    known_ids = {item.id for item in evidence}
    return ProblemList(problems=rank(clean_citations(result.problems, known_ids)))
