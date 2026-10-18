# Case study

Case ID: F3-steam-scan-check
Classification: failure
Run record: artifacts/agent/runs/q4-missing-20261018T140315Z.json
Repaired by: artifacts/agent/runs/q4-missing-20261018T141746Z.json
Code revision: 8be0b6f6e8ebd9bd3b72c38879ca8b406d88c9b6 (with uncommitted changes)
Reviewer: Drafted by Claude Code (coding agent), 2026-10-18, from artifacts/match/matches.json, artifacts/compare/facts.json, artifacts/compare/comparison.json and the scan images. Checked and approved by the team's only member, 2026-10-18.

## Question

What does the Britannica sample say about the steam locomotive?

## Evidence

The sample has no locomotive entry. The closest entry is page-0523-a583606e375a:e15 (ENGINE), uncertain match to 'Engine'. OCR text: 'turned into fleam'. The printed page shows 'ſteam': the reviewer read it from a 4x crop of page-0523-a583606e375a.jpg, box x 298-552, y 50-145. The first run called vision_analyze with region [298,50,552,145] (254x95 pixels) and asked whether the last word was 'steam' or 'fleam'. Direct Super VL test with a neutral question (evaluation/vision_check.json): the same crop read 'ſteam' at 1x and at 4x.

## Result

The first run correctly says that the evidence for a steam locomotive is missing. It also says it verified the scan and that the printed page reads 'fleam'. That is false. The repaired run used the enlarged crop and asked for a transcription without the OCR reading. It reported 'raise' and 'steam', which matches the print, and it still said the locomotive evidence is missing.

### Limits

Inference from one case: the neutral 1x test read the word correctly, so the leading question in the first run is the more likely cause than the image size. The repaired answer still calls -6.0 the 'accept floor'; the accept threshold is -3.5 and the floor is -6.0. This case and F1 share the scan check step, so they are not independent failures. The repair worked here and did not work for F1. The first six runs used the earlier scan tool, which gave only image_path and region, and five evidence rules; the challenge_scan output in each run record shows which version was live.
