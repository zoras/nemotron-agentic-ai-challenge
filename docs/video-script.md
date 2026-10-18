# Video script

Team: Dhaubaji (Prabesh Shrestha and Saroj Maharjan)
Length: 4 minutes 46 seconds. The limit is 3 to 5 minutes.
Narration: about 620 words, which take 4 minutes 26 seconds with the edge-tts voice `en-GB-RyanNeural`.
The times below come from the produced video. A title card opens each section.
If a live take runs over 5 minutes, cut the ABYSSINIA line in section 2.

Every number in this script comes from `README.md`, `templates/submission.md` or the committed artifacts.
Each section names its source.
Do not add numbers that are not in this script.

## Before you record

Open these tabs in this order.
`SITE` means https://prabeshsb.github.io/nemotron-agentic-ai-challenge/.
`REPO` means https://github.com/prabeshsb/nemotron-agentic-ai-challenge/blob/main/.

1. `SITE/index.html` (Overview)
2. `SITE/pages/page-0251-69952e7c4a0f.html` (scan page with Switzerland, SWORD and SYDENHAM)
3. `SITE/scans/page-0251-69952e7c4a0f.jpg` (the raw scan image)
4. `REPO/artifacts/match/matches.json` (search for `page-0251-69952e7c4a0f:e8`)
5. `REPO/artifacts/evaluate/match_calibration.json` (search for `embedder_vs_reranker`)
6. `SITE/analysis.html`
7. `SITE/agent.html`
8. `REPO/evaluation/vision_check.json`
9. `SITE/scans.html`
10. `SITE/documents/page-0251-69952e7c4a0f.pdf`
11. `REPO/templates/submission.md`

Set the browser zoom so that one scan column fills the screen.
Record the screen at 1080p or higher.

## Timeline

| Time | Section | Rubric item | Points |
| --- | --- | --- | --- |
| 0:00 to 0:17 | 0. Opening | | |
| 0:17 to 0:51 | 1. Parse the scans | Parse | 15 |
| 0:51 to 1:21 | 2. Super VL plans the matches | Super VL | 20 |
| 1:21 to 2:11 | 3. Embed, rerank and calibrate | Embed+Rerank | 15 |
| 2:11 to 3:00 | 4. Compare vocabulary, topics and facts | Creativity | 20 |
| 3:00 to 4:01 | 5. Hermes agent: one success, one failure | Hermes | 10 |
| 4:01 to 4:21 | 6. Website and LaTeX documents | Completion | 20 |
| 4:21 to 4:46 | 7. Limits and close | | |

Super VL also appears in sections 4 and 5. Name it each time.

## 0. Opening (0:00 to 0:17)

On screen: tab 1, the Overview. Point at the row of counts.

Narration:

> We are team Dhaubaji: Prabesh Shrestha and Saroj Maharjan.
> We matched 100 scans of the early Encyclopaedia Britannica to Wikipedia and compared what they say.
> Every number here comes from saved model replies in the repository.

Source: `README.md`, table "Our solution".

## 1. Parse the scans (0:17 to 0:51), rubric item Parse

On screen:

1. Tab 3, the raw scan of page 0251. Point at the two columns and the long s.
2. Tab 2, the scan page. Scroll from "Switzerland (continuation, e1)" to "SWORD (headword, e4)" and "SYDENHAM (headword, e8)".
3. Point at the links "raw Parse replies" and "Compiled LaTeX document (PDF)" near the top.

Narration:

> Nemotron Parse 3.5 first reads the full page for layout.
> Then it reads each column as a masked crop at three times the size, so the two columns do not mix.
> We classify pages by ink, so we drop any text that Parse invents on an empty page.
> Result: 88 text pages, 9 plates, 2 covers and 1 blank, with 0 unfinished regions.
> We split the text into 284 entries, each with its page ID, scan checksum and raw Parse reply.

Source: `README.md` Extract row; `templates/submission.md` "Scan coverage and extraction".

## 2. Super VL plans the matches (0:51 to 1:21), rubric item Super VL

On screen:

1. Tab 4, `matches.json`. Show the `models` block: `"plan": "nvidia/Nemotron-3.5-Super-VL"`.
2. Show the `method.plan` line: "Super VL reads the top of the scan and the entry text and proposes titles and queries".
3. Search for `page-0251-69952e7c4a0f:e8` and show the SYDENHAM decision.

Narration:

> Nemotron 3.5 Super VL reads the top of each scan and the entry text, and proposes modern Wikipedia titles and keywords.
> For example, the ABYSSINIA fragment matched the article "Ethiopian Empire".
> BM25 search adds keyword candidates.
> Super VL also writes our fact claims and runs the Hermes agent.
> SYDENHAM matched "Thomas Sydenham" with a rerank logit of 0.88 and a margin of 1.98.

Source: `artifacts/match/matches.json` (`models`, `method`); case S1 in `evaluation/review.json`.

## 3. Embed, rerank and calibrate (1:21 to 2:11), rubric item Embed+Rerank

On screen:

1. Tab 4, `matches.json`. Show `"rerank_docs": 32` and the six groups under `thresholds`.
2. Tab 5, `match_calibration.json`. Show `by_decision`, then `embedder_vs_reranker`.
3. Show one example from `embedder_vs_reranker.examples`: "Imperial units" (reranker, correct) against "Metrication in the United Kingdom" (embedder) for WEIGHTS AND MEASURES.

Narration:

> The Nemotron embedder and reranker ran on a Nebius GPU endpoint.
> The embedder orders all candidates, and the reranker scores the best 32.
> Reranker scores vary by query type, so six groups get their own thresholds, set from 540 hand-labelled candidates.
> Of 284 topics, 202 are accepted, 60 uncertain and 22 have no match.
> 210 of 217 labelled accepted matches are correct. That is in-sample, because the same labels set the thresholds.
> Where the reranker and the embedder disagree and both are labelled, the reranker alone is right 19 times and the embedder alone 22 times.
> So the reranker did not beat the embedder, and we report that.

Source: `README.md` Match row and "Known limits"; `artifacts/evaluate/match_calibration.json`.

## 4. Compare vocabulary, topics and facts (2:11 to 3:00), rubric item Creativity

On screen:

1. Tab 6, the analysis page. Show the header line with 219 pairs and 3,628 long-s changes.
2. Show "Words each source uses more" and the figure `distinctive-words.png`.
3. Scroll to "Spelling normalisation": "fo" to "so", "thefe" to "these", "fame" to "same" (context rule).
4. Show the topic table. Point at topic 2 ("long lat, lat, town, situated"), with 22 Britannica and 2 Wikipedia documents.
5. Tab 2, the scan page. Scroll to the SYDENHAM "Fact checks" table with the check marks. Section 5 refers to it.

Narration:

> Across 219 matched pairs, we first normalise the long s: "thefe" becomes "these", and a context rule decides when "fame" means "same". We record all 3,628 changes.
> Britannica prefers words like "manner", "parts" and "likewise". Wikipedia prefers "century", "population" and "modern".
> A joint topic model on Nemotron embeddings shows clusters like this one, places given by latitude and longitude: 22 Britannica entries, 2 Wikipedia articles.
> Super VL writes fact claims with a quote from each source, and we check each quote in the text.
> Of 637 claims, 146 agree, 102 differ and 389 are not found.

Source: `artifacts/compare/comparison.json` (`counts`, `text_changes`, `distinctive_words`, `topics`); `artifacts/compare/facts.json` (`counts`).

Note: the word lists are from the content-word lists on the analysis page. Read them as they appear on screen.

## 5. Hermes agent: one success, one failure (3:00 to 4:01), rubric item Hermes

On screen:

1. Tab 7, the agent page. Show the S1 Sydenham card.
2. Scroll to the F1 sword card.
3. Tab 2, the scan page. Show the SWORD OCR text: "ferving either to cut or flatb".
4. Tab 3, the raw scan. Zoom in on the SWORD entry, where the print says "ſtab".
5. Tab 8, `vision_check.json`. Show `"scale": 1` with "ſlab" and `"scale": 4` with "ſtab".

Narration:

> The agent is Hermes with Super VL and five tools over our saved, cited evidence.
> We asked six questions and reviewed every answer.
> Success, S1: on Thomas Sydenham, the agent quotes the four checked claims from both sources, and calls three uncovered Britannica details unverified, not false.
> Failure, F1: Parse read "to cut or ſtab" as "flatb". We asked the agent to check the scan.
> Its crops were only 30 to 187 pixels high, and the question offered the OCR word. It confirmed "flatb". Wrong.
> A direct Super VL test read "ſlab" at page size and "ſtab" at four times.
> So we sent a crop at four times the size and a neutral question. That fixed the steam case, F3, but not the sword.
> The model called the image blurry and reported "thrust". We infer that a fact claim in its context led it there. We kept both failed runs.

Source: cases S1, F1 and F3 in `evaluation/review.json`; `evaluation/vision_check.json`; `docs/hermes.md`.
The narration labels the cause of the sword failure as an inference, as `review.json` does.

## 6. Website and LaTeX documents (4:01 to 4:21), rubric item Completion

On screen:

1. Tab 9, the scans list. Scroll down to show all 100 rows with status and match counts.
2. Click one plate row, then go back.
3. Tab 10, the PDF of page 0251. Scroll one page.
4. Tab 11, `submission.md`. Show the repository, website and documents lines.

Narration:

> The website has a page for each of the 100 scans, an analysis page and the agent cases.
> Each scan has a LuaLaTeX document: 100 of 100 compiled, with 0 missing glyphs.
> 147 tests pass, and the repository keeps every raw model reply.

Source: `README.md` Site row; `templates/submission.md` "Limits".

## 7. Limits and close (4:21 to 4:46)

On screen: tab 1, the Overview. Then the repository README, section "Known limits".

Narration:

> Three limits.
> Match precision is in-sample, and a coding agent wrote the labels.
> "Not found" means not in the saved passages of one article, not that Wikipedia omits it.
> And the agent can still trust its context over the scan.
> Everything is in the repository. Thank you.

Source: `README.md` "Known limits"; `templates/submission.md` "Limits".

## After you record

1. Check with `ffprobe` that the video is between 3 and 5 minutes, 1920x1080 and 30 fps.
2. Publish the MP4 as an asset of the GitHub release `video-v1`, named "Hackathon video". Do not commit the MP4.
3. Put the asset URL in the "Video URL" line of `templates/submission.md`.
