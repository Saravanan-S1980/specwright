# Specwright

Specwright turns messy product inputs into a spec you can build from, and then into a prototype you can click.

Feed it support tickets, interview notes, SOPs or a one-line idea. It finds the real problems, defines features with testable acceptance criteria, writes the PRD, maps the UX flows and generates a clickable prototype. Every screen traces back to the ticket or interview line that justified it.

> Status: week 1 of a 12-week public build. Follow along in the commit history.

## Pipeline

| Stage | Input | Output |
| --- | --- | --- |
| 1. Ingest | Files of any supported type | Evidence store with source tags |
| 2. Synthesize | Evidence | Ranked problem list with cited evidence |
| 3. Define | Chosen problems | Features, user stories, acceptance criteria, RICE |
| 4. Specify | Features | PRD with citations |
| 5. Design | Stories | Screen inventory and user flows |
| 6. Prototype | Screen specs | Clickable React prototype |

A human approves the output of every stage before the next one runs.

## AI concepts in this repo

Structured output, embeddings, hybrid RAG, tool use, agent loops, multi-agent orchestration, the Claude Agent SDK harness, MCP server and client, skills, memory, human-in-the-loop gates, guardrails against prompt injection, model routing, vision, tracing and evals. Each one is tied to a real job in the pipeline. See `docs/decisions/` for why each choice was made.

## Evals

Quality is measured, not assumed. The first golden dataset is 200 synthetic support tickets for a fictional clinic-booking app, with 8 problems planted at known frequencies. The synthesis stage is scored on how many it finds.

| Version | Planted problems found | Date |
| --- | --- | --- |
| v0 baseline | _pending_ | |

## Run it

```bash
cd backend
pip install -e ".[dev]"
export ANTHROPIC_API_KEY=sk-ant-...
pytest
uvicorn app.main:app --reload
```

## License

MIT
