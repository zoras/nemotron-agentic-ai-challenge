# Case study

Case ID: F2-language-change-topics
Classification: failure
Run record: artifacts/agent/runs/q2-language-change-20261018T140210Z.json
Code revision: c2c17299241a934d2c41438e940681b578646ebe (with uncommitted changes)
Reviewer: Claude Code (coding agent), 2026-10-18. Each verdict was checked against artifacts/match/matches.json, artifacts/compare/facts.json, artifacts/compare/comparison.json, and the scan images. Not yet checked by a team member.

## Question

Across the matched pairs, which words does the Britannica use far more than Wikipedia, and what do they show about how the language or the knowledge changed?

## Evidence

challenge_corpus returned the word lists, the counts (219 pairs, 3,628 long-s changes, median lift 2.541) and the topic clusters. In artifacts/compare/comparison.json topics.topics, topic 12 has terms erector, englith, anatomy, engine, forlorn, pound, model, penis; 25 Britannica and 0 Wikipedia documents; examples SYCAMORE-TREE, JIN, ENGINE, ENEMY, ENFANS PERDUS, OUNCE. Topic 4 has terms pressure, blood, blood pressure, anatomy, heart, body; 2 Britannica and 9 Wikipedia documents.

## Result

The word lists and counts in the answer are correct. The interpretation is not. The answer calls topic 12 'anatomy/engineering' and uses it as evidence that Britannica text centres on physical description. Its examples show a mixed group of short dictionary headwords with OCR noise ('englith'), not a subject. The answer gives topic 4 (blood pressure, anatomy) as an example of Wikipedia's 'period/place/demographic framing', which that topic does not show. The answer labels its conclusion as an inference, but two of the clusters it cites do not support it.

### Limits

The run record keeps about 5,000 characters of each tool output, so topic 12 is not in the record. The full output (9,260 characters) is in the Hermes session 20261018_160212_9cf4b1 in data/hermes/state.db, which is not committed. The reviewer checked topic 12 against artifacts/compare/comparison.json, from which the agent index was built. Inference: the model read the top terms 'anatomy' and 'engine' and did not use the examples; the topic rows have no labels. No repair was run.
