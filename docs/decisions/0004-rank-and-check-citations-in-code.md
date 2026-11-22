# 0004: Claude groups, code ranks and checks citations

Date: 2026-11-22

## Context
The synthesize stage turns tickets into a ranked problem list. Some of that work needs judgment: deciding that "reminder came after my visit" and "SMS a day late" are the same problem. Some of it is arithmetic: counting tickets, sorting, checking that each cited ID exists.

Models are good at the first kind and unreliable at the second. They miscount long lists and sometimes cite IDs that aren't in the input.

## Decision
Claude only groups tickets and labels each group. Plain Python does the rest:

- `rank()` sorts by number of tickets, then by severity.
- `clean_citations()` drops any evidence ID that isn't in the input, drops duplicates, and drops a problem left with no evidence.
- `format_evidence()` escapes ticket text before wrapping it in `<ticket id="...">` tags, so a ticket containing `</ticket>` can't break out of its tag.

The prompt tells Claude that ticket text is data and never instructions, and that it doesn't need to rank.

## Alternatives considered
- Ask Claude to rank: one less function, but the order could silently disagree with the counts, and you'd only notice by recounting by hand.
- Reject the whole answer when an ID is made up: stricter, but one bad ID would throw away an otherwise good list. Dropping the bad ID keeps the rest and stays honest.
- Tags without escaping: fine for most data, but it leaves an easy prompt-injection path open.

## Consequences
Rankings are reproducible and testable without a model. Every cited ID is guaranteed to exist. We don't see how often Claude makes up IDs, since we quietly drop them. If the eval shows bad citations matter, log the dropped IDs.
