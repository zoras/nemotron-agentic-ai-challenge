# Case study

Case ID: S1-sydenham-facts
Classification: success
Run record: artifacts/agent/runs/q1-sydenham-facts-20261018T140143Z.json
Code revision: 8be0b6f6e8ebd9bd3b72c38879ca8b406d88c9b6 (with uncommitted changes)
Reviewer: Drafted by Claude Code (coding agent), 2026-10-18, from artifacts/match/matches.json, artifacts/compare/facts.json, artifacts/compare/comparison.json and the scan images. Checked and approved by the team's only member, 2026-10-18.

## Question

What does the early Britannica say about Thomas Sydenham, and which of its facts does the matched Wikipedia article confirm or contradict?

## Evidence

Britannica entry page-0251-69952e7c4a0f:e8 (page_id britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:251). Match: topic accepted to Wikipedia 'Thomas Sydenham' (page_id 564669, revision_id 1341167433), rerank logit 0.88, margin 1.98 (artifacts/match/matches.json). Fact check (artifacts/compare/facts.json): 4 claims, all 'agrees' with britannica_quote_found and wikipedia_quote_found true: born about 1624 at Winford Eagle; bachelor of physic in 1648; fellow of All Souls soon after; died 1689.

## Result

The answer cites the entry, page and revision IDs. It quotes the four checked claims with both quotes and reports no contradiction. It names three Britannica details that the saved Wikipedia passages do not cover: the father's name, 'chief physician in London from 1660 to 1670', and the Oxford garrison story. It calls them unverified, not false.

### Limits

The agent also called six more details 'confirmed in substance' from passages that it read with challenge_passages. The facts stage did not check these, and the reviewer did not check every passage offset. The agent did not check the scan; it said the words it needed were legible in the OCR text.
