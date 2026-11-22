# 0001: Start evals with a synthetic dataset that has planted answers

Date: 2026-11-22

## Context
Stage 2 (synthesize) turns tickets into a ranked problem list. To know if a prompt change helps or hurts, we need a dataset where the right answer is known.

## Decision
Generate 200 support tickets for a fictional clinic-booking app, CareSlot. Plant 8 problems at frequencies 30, 22, 18, 14, 10, 8, 6 and 4. The other 88 tickets are one-off noise. The generator has a fixed seed and its output is committed.

## Alternatives considered
- Public ticket datasets: realistic, but nobody knows the "true" problem list, so scoring is subjective.
- Hand-written tickets: slow, and too easy to write them in a way that suits the prompt.

## Consequences
Scoring is objective: found N of 8, ranked in the right order or not. The risk is that template phrasing is easier than real tickets. Week 2 adds a messier, hand-written set to catch that.
