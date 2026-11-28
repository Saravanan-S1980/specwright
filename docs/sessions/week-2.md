# Week 2 sessions

Start each in a **new** session on the `specwright` environment, Sonnet 5.5. End every session with: "Open a pull request and explain each file in plain words."

Baseline from week 1 (`synthesize_v1`, Sonnet 5.5): found 7 of 8, covered 8 of 8, noise cited 50 of 88, $0.07 per run.

## Session 5: fix the dataset before fixing the prompt

The 50-of-88 noise score is mostly a dataset bug. The generator draws 88 noise tickets from only 15 templates, so each "noise" theme repeats about 6 times, and "password reset email never arrives" five times is a real problem. Claude was right to report it.

> Create `evals/datasets/clinic_tickets_v2/` with its own generator. Keep the same 8 planted problems, counts and phrasings as v1. Replace the noise with 88 one-off tickets: every noise ticket is about a different topic, and no two could reasonably be grouped as one problem. Write the generator so this holds by construction (one list of 88 distinct subject/body pairs, each used once). Add a test that fails if two noise tickets share a subject. Keep v1 untouched for history. Point `run_evals.py` at a `--dataset` argument, defaulting to v2. Run the eval on v2 with `synthesize_v1` and add a row to the README table. Add ADR 0005 explaining why v1's noise was flawed.

## Session 6: let one problem hold its variants

Claude split late reminders into three problems (SMS after the visit, wrong time zone, next-morning push). For an engineer those are three causes; for a PM they're one problem. Keep both views.

> Add an optional `variants: list[Variant]` field to `Problem`, where `Variant` has `title` and `evidence_ids`. Write `prompts/synthesize_v2.md`: group by the problem the user experiences, and when the tickets show different causes or channels for the same problem, list them as variants inside one problem instead of separate problems. Keep v1 in place. Make the prompt version selectable in `run_evals.py` with `--prompt`. Run v1 and v2 on clinic_tickets_v2 and add both rows to the README. Report whether found went up and whether anything else got worse.

## Session 7: model routing, measured

> Move the price table from `run_evals.py` into `config.py` and add cost per call to the traces in `llm.py`. Add `--model` to `run_evals.py`. Run synthesize_v2 on clinic_tickets_v2 with Haiku 5.5 and Sonnet 5.5. Add both rows to the README. Write ADR 0006 on model routing: which model each stage uses and why, with these numbers as evidence.

## Session 8: your first MCP server

> Create `mcp_server/` using the official MCP Python SDK (FastMCP). Expose two tools: `synthesize_tickets(csv_text: str)` that runs ingest + synthesize and returns the ranked problem list as JSON, and `list_datasets()` that lists the golden datasets. Reuse the backend code; don't duplicate logic. Treat the CSV as untrusted data, same as the API does. Add tests that call the tool functions directly with the model mocked. Add a README section showing how to connect it to Claude Desktop and Claude Code with a config snippet. Explain what MCP is and how this differs from our FastAPI route.

After merging, connect it to Claude Desktop on your laptop and ask Claude: "Use specwright to find the problems in this CSV." That's the moment the concept clicks.

## End of week checklist

- [ ] README eval table has v0, v1-on-v2-data, v2, and Haiku vs Sonnet rows
- [ ] ADRs 0005 and 0006 merged
- [ ] Specwright MCP server answers a question in Claude Desktop
- [ ] LinkedIn post: "My eval said Claude was wrong. The eval was wrong."
