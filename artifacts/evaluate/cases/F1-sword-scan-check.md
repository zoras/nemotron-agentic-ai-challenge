# Case study

Case ID: F1-sword-scan-check
Classification: failure
Run record: artifacts/agent/runs/q5-scan-check-20261018T140345Z.json
Code revision: f869e67191e89b3569678643175e1b32b5bdc59f (with uncommitted changes)
Reviewer: Drafted by Claude Code (coding agent), 2026-10-18, from artifacts/match/matches.json, artifacts/compare/facts.json, artifacts/compare/comparison.json and the scan images. Checked and approved by team member Prabesh Shrestha, 2026-10-18.

## Question

Find the Britannica entry on the sword. Check one doubtful OCR word against the scan image, and report what the printed page shows.

## Evidence

OCR text: 'serving either to cut or flatb'. The printed page shows 'ſtab': the reviewer read it from a 4x crop of page-0251-69952e7c4a0f.jpg, box x 298-563, y 205-260. The run made three vision_analyze calls on page-0251-69952e7c4a0f.jpg with pixel regions [298,211,563,398], [440,235,565,280] and [330,226,490,256]. Hermes crops the region without enlarging it, so the model received images of 265x187, 125x45 and 160x30 pixels. Each question asked whether the word was 'flatb' or 'thrust'. Direct Super VL test with a neutral question (evaluation/vision_check.json): the same crop read 'ſlab' at 1x and 'ſtab' at 4x.

## Result

The answer says that the print shows 'flatb' and that the OCR did not misread the word. It infers the intended word 'thrust'. All three statements are wrong: the page prints 'ſtab'. The answer also calls the 1.158 margin a margin 'over the accept floor -6.0'; the tool reason gives it as the margin over the next candidate.

### Limits

Repair attempt: the scan tool now gives an enlarged crop (crop_path, 4x) and tells the agent not to put the OCR reading in its question. The repaired run artifacts/agent/runs/q5-scan-check-20261018T141816Z.json also failed. Its first vision call sent the whole crop; the image header in the run record shows Hermes passed it as a 1060x748 JPEG, so the model received the enlarged image. The model wrote 'The zoom is too blurry to read the individual letters with certainty', then reported that the page 'clearly shows t-h-r-u-ſ-t'. Inference: the fact claim 'used for cutting or thrusting', which challenge_compare returned before the vision call, anchored the reading. That claim is Super VL's paraphrase of the garbled OCR text, not a reading of the print. Two other attempts (q5-scan-check-20261018T141719Z.json and q4-missing-20261018T141715Z.json) failed with HTTP 401 because the run script did not load .env; their records are kept. The repair is not complete. The first six runs used the earlier scan tool, which gave only image_path and region, and five evidence rules; the challenge_scan output in each run record shows which version was live.
