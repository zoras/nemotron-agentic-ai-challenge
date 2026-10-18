# Case study

Case ID: S3-uncertain-matches
Classification: success
Run record: artifacts/agent/runs/q6-uncertain-20261018T140538Z.json
Code revision: 8be0b6f6e8ebd9bd3b72c38879ca8b406d88c9b6 (with uncommitted changes)
Reviewer: Drafted by Claude Code (coding agent), 2026-10-18, from artifacts/match/matches.json, artifacts/compare/facts.json, artifacts/compare/comparison.json and the scan images. Checked and approved by the team's only member, 2026-10-18.

## Question

Which entries could not be matched with confidence, and why? Give two examples with their evidence.

## Evidence

Corpus counts: topic decisions accepted 202, uncertain 60, no_match 22 (artifacts/match/matches.json counts). page-0523-a583606e375a:e14: no_match, 'reranker logit -4.89 against accept -2.0 and floor -4.5 for topic/headword, margin 0.21 over the next candidate, found only by keyword search'. page-0523-a583606e375a:e15: uncertain, 'reranker logit -4.35 against accept -3.5 and floor -6.0 for topic/headword, margin 0.42 over the next candidate'.

## Result

The answer gives the counts and two examples. Each example has the entry ID, page ID, proposed article, logit, the group threshold, margin, and the search route, all as the tool reported them. It does not treat either match as evidence of the same topic. It says that the tools cannot list all 82 entries.

### Limits

For e14, the article 'Engine' was a candidate at logit -5.10 and 'Machine' at -5.95, below 'History of engineering' at -4.89 (artifacts/match/matches.json ranked list). The agent could not see this, because challenge_compare returns only the chosen article and the runner-up. The entry defines an engine as 'a compound machine, made of one or more mechanical powers'. Inference: the Wikipedia article 'Engine' describes a motor, a narrower modern sense, so the reranker found no close article. The plugin has no tool that lists unmatched entries.
