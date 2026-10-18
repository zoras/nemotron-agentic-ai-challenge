# Submission

Team: Dhaubaji
Repository URL and commit: https://github.com/prabeshsb/nemotron-agentic-ai-challenge, branch `extract-stage`, commit `d060bce` (code, docs and artifacts)
Video URL, 3 to 5 minutes: TODO
Static website URL: https://prabeshsb.github.io/nemotron-agentic-ai-challenge/ (GitHub Pages, branch `gh-pages`, built from `d060bce`)
Compiled LaTeX documents: 100 PDFs at https://prabeshsb.github.io/nemotron-agentic-ai-challenge/documents/ (local copy in `site/documents/`), one for each scan, with their `.tex` sources. Build record: `site/build.json`.

## Reproduce the run

Setup and run commands are in the README section [Reproduce](../README.md#reproduce).
Hermes setup is in [docs/hermes.md](../docs/hermes.md).

Tested versions:

- Python 3.12.12 on macOS.
- httpx 0.28.1, lancedb 0.40.0, numpy 2.5.4, pillow 11.3.0, pyarrow 21.0.0, scikit-learn 1.9.1, umap-learn 0.5.12, wordfreq 3.1.1, matplotlib 3.11.2. `uv.lock` pins every package.
- Hermes Agent v0.22.2 (2026.9.24).
- LuaLaTeX with the STIX Two Text font.

Models and serving:

- Parse: `nvidia/nemotron-3.5-parse`, organizer endpoint.
- Embedder: `nvidia/llama-nemotron-embed-vl-1b-v2`, revision `582e3bf72aee355e3c59ed89de53543c5b0657ee`.
- Reranker: `nvidia/llama-nemotron-rerank-vl-1b-v2`, revision `b8a9987b05b75db5ad949c825cbcbf6eb7c48b5a`.
- Embedder and reranker ran on a Nebius Serverless endpoint: one NVIDIA RTX PRO 6000 Blackwell GPU, platform `gpu-rtx6000-a`, preset `1gpu-24vcpu-218gb`, region `uk-south2`, bfloat16. The endpoint record is in `infra/nebius/deployment.json`. The smoke receipt is in `runs/`. We deleted the endpoint after the runs.
- Super VL: `nvidia/Nemotron-3.5-Super-VL` on Nebius Token Factory. It plans matches, writes fact claims, and runs the Hermes agent.

Data:

- Britannica: `NationalLibraryOfScotland/encyclopaedia_britannica_illustrated`, revision `309f765b1ecc83e0a7f7762e44b4a927a7555443`.
- Britannica manifest SHA-256: `779542e078756874f23fa6971d7d8a2d8635ad6d9d9484e1deb607d94a28e396`.
- Source Parquet SHA-256: `08f167015db23cb027995b2b6a6bc953b01d7c1ddf667de950465cc2b601af5c`.
- Wikipedia snapshot revision: `417c267bb457fa645c22eb3b5c77764963194c70`.

The full record is in `artifacts/evaluate/reproducibility.json`.

## Results

Scan coverage and extraction:

- Parse read all 100 scans: 88 text pages, 9 plates, 2 covers, 1 blank page.
- 285 region replies, 0 unfinished regions.
- 284 entries: 201 headwords and 83 continuations. 22 entries are cross-references and 20 have no title.
- Each entry keeps its page ID, block IDs, scan checksum, and the raw Parse reply.

Article associations:

- 340 targets: 284 topics and 56 subtopics of continuation pages.
- Topic decisions: 202 accepted, 60 uncertain, 22 no match.
- Subtopic decisions: 17 accepted, 26 uncertain, 13 no match.
- 279 Wikipedia articles, each with its page ID, revision ID, and text checksum.
- A hand check of 540 candidates found 210 of 217 accepted topic targets correct. This figure is in-sample.
- The match rule rejects disambiguation and list pages.

Comparison method:

- Text unit: one accepted match, one Britannica entry against one Wikipedia article. 219 pairs.
- Normalisation: markup removal, joins at line-end hyphens, lower case, long-s folding (3,628 changes, 161 of them from context rules), and 6 historical spellings. Each change is counted.
- Exclusions: 3,627 Britannica tokens that are unknown to `wordfreq`, which are OCR errors or obsolete words.
- Analyses: vocabulary lift against unrelated articles (median 2.541), distinctive words by log-odds with an informative Dirichlet prior, joint topics over Nemotron embeddings, and fact claims from Super VL with quotes checked in both sources.
- Fact claims: 637 claims over 164 pairs. 146 agree, 102 differ, 389 not found. 1 request failed and is recorded.

Links:

- Analysis page: `site/analysis.html`, with plots in `site/figures/`.
- Source records: `artifacts/extract/entries.json`, `artifacts/match/matches.json`, `artifacts/compare/comparison.json`, `artifacts/compare/facts.json`.

## Case studies

The review is in `evaluation/review.json`. One case study per case is in `artifacts/evaluate/cases/`.

| Case | Run record | Summary |
| --- | --- | --- |
| [S1 success](../artifacts/evaluate/cases/S1-sydenham-facts.md) | `q1-sydenham-facts-20261018T140143Z.json` | Four checked Sydenham facts quoted from both sources. Unverified details kept apart. |
| [S2 success](../artifacts/evaluate/cases/S2-abyssinia.md) | `q3-abyssinia-20261018T140239Z.json` | Abyssinia fragment compared with "Ethiopian Empire". Britannica-only claims labelled. |
| [S3 success](../artifacts/evaluate/cases/S3-uncertain-matches.md) | `q6-uncertain-20261018T140538Z.json` | Two uncertain ENGINE matches explained with the logged thresholds. |
| [F1 failure](../artifacts/evaluate/cases/F1-sword-scan-check.md) | `q5-scan-check-20261018T140345Z.json` | Vision check confirmed the OCR error "flatb". The print says "ſtab". The repair run also failed. |
| [F2 failure](../artifacts/evaluate/cases/F2-language-change-topics.md) | `q2-language-change-20261018T140210Z.json` | A mixed cluster of short headwords read as an anatomy topic. |
| [F3 failure](../artifacts/evaluate/cases/F3-steam-scan-check.md) | `q4-missing-20261018T140315Z.json` | Correct "evidence missing" answer with a false scan reading. Repaired by `q4-missing-20261018T141746Z.json`. |

The run records are in `artifacts/agent/runs/`.
Two repair attempts that failed with `HTTP 401` are kept there too.

## Limits

What we tested:

- 147 automated tests cover the data contracts, each stage on small fixtures, the Hermes tools, and the review checks. They do not measure OCR accuracy or retrieval quality.
- The hand labels measure match quality. One coding agent wrote them, and the team member checked the agent cases.
- Direct vision tests in `evaluation/vision_check.json` compare small and enlarged scan crops.

What remains uncertain and known failure modes:

- The thresholds and their precision come from the same labels, so the precision is in-sample.
- The reranker does not choose the first candidate better than the embedder. Where they disagree and both choices are labelled, the reranker alone is right 19 times and the embedder alone 22 times.
- Parse reads the long s plus t ligature as "fl" in 2 of 2 checked cases. Normalisation keeps the result when it is a real word, for example "fleam".
- `not_found` means the claim is not in the saved passages of one article, not that Wikipedia omits it.
- The agent can repeat a word from its context instead of reading the scan, even with an enlarged crop (case F1).
- The agent reads topic clusters from their top terms and can give a mixed cluster a subject name (case F2).
- The agent run records keep about 5,000 characters of each tool result. The full results are in the local Hermes session database.

Possible next steps:

- Hold out part of the labels to measure the thresholds out of sample.
- Run the vision check before the agent sees the fact claims, or in a separate session with only the crop.
- Give each topic cluster a label from its examples, and mark clusters that consist mostly of OCR noise.
- Copy the full tool results from the Hermes session database into each run record.
