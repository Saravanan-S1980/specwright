# 0002: Read the API key from SPECWRIGHT_API_KEY first

Date: 2026-11-22

## Context
The build runs in Claude Code cloud sessions. `ANTHROPIC_API_KEY` was set as an environment variable on the cloud environment, but it never showed up inside sessions, even new ones. Claude Code uses that name for its own authentication, so the session doesn't expose it to our code.

## Decision
The app reads `SPECWRIGHT_API_KEY` first and falls back to `ANTHROPIC_API_KEY`. The value lives in `config.settings.api_key`, and `llm.py` passes it to the Anthropic client explicitly.

## Alternatives considered
- Network secret for api.anthropic.com: the cloud proxy never attaches secrets to Anthropic API requests, so this doesn't work.
- Only `ANTHROPIC_API_KEY`: works on a laptop, fails in every cloud session.

## Consequences
Works in cloud sessions and locally. Anyone cloning the repo can use either name.
