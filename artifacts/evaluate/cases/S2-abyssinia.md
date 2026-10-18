# Case study

Case ID: S2-abyssinia
Classification: success
Run record: artifacts/agent/runs/q3-abyssinia-20261018T140239Z.json
Code revision: c2c17299241a934d2c41438e940681b578646ebe (with uncommitted changes)
Reviewer: Claude Code (coding agent), 2026-10-18. Each verdict was checked against artifacts/match/matches.json, artifacts/compare/facts.json, artifacts/compare/comparison.json, and the scan images. Not yet checked by a team member.

## Question

How does the Britannica account of Abyssinia compare with Wikipedia? Name the pages and articles you rely on.

## Evidence

Britannica continuation entry page-2570-364adfefc0b1:e1 (page_id britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:2570). Match: topic accepted to Wikipedia 'Ethiopian Empire' (page_id 9602302, revision_id 1353434359), rerank logit 1.74, margin 0.04 over 'Abyssinia' (artifacts/match/matches.json). Vocabulary: entry coverage 0.3792 against baseline 0.0961, lift 3.947 (artifacts/compare/comparison.json). Fact check (artifacts/compare/facts.json): 4 claims, all 'not_found' with britannica_quote_found true and wikipedia_quote_found false.

## Result

The answer names both sources with IDs. It describes the difference in scope: the Britannica fragment covers a court episode from 1706 to 1709, and the Wikipedia article covers the empire from 1270 to 1974. It reports the four claims as Britannica-only, not as errors. It lists what the saved evidence cannot answer, and it says that it did not check the scan.

### Limits

The match margin is 0.04, so 'Abyssinia' was almost chosen. Inference: both titles describe the same state. The fact check reads only the saved passages of one article. The pipeline did not look for other Wikipedia articles, for example about the rulers named in the fragment, so 'not_found' does not mean that Wikipedia omits these events.
