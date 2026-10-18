# Hermes agent

Hermes Agent runs the comparison agent.
The main model is `nvidia/Nemotron-3.5-Super-VL` on Nebius Token Factory.
The agent answers from saved project artifacts through five native tools.
It does not call the pipeline models or the Wikipedia API during a run.

We tested this setup with `Hermes Agent v0.22.2 (2026.9.24)`.

## Set up a separate profile

Install Hermes Agent with the [official instructions](https://hermes-agent.nousresearch.com/docs/getting-started/installation).
Record the installed version with `hermes --version`.
Run the following commands from the repository root.

```bash
export HERMES_HOME="$PWD/data/hermes"
mkdir -p "$HERMES_HOME/plugins"
cp integrations/hermes/config.example.yaml "$HERMES_HOME/config.yaml"
cp -R integrations/hermes/nemotron-challenge "$HERMES_HOME/plugins/"
hermes plugins enable nemotron-challenge
```

Keep `data/hermes` out of Git.
It contains conversations, the session database, and provider settings.

The config selects the named custom provider `tokenfactory-super`.
It reads the key from `SUPER_API_KEY` through `key_env`.
Set `SUPER_API_KEY` in the root `.env` file.
Hermes gets the key only from its environment.
If the environment does not have the key, each run stops after about 3 seconds with `HTTP 401`.
The `agent` stage loads `.env` before it starts Hermes.
A script that calls `agent.run_question` must call `Settings.from_env()` first.

## Tools

The plugin is in `integrations/hermes/nemotron-challenge`.
It uses the Python standard library only, because Hermes runs in its own environment.
It reads `artifacts/agent/index.json`, which the `agent` stage builds from the saved stage outputs.

| Tool | Input | Result |
| --- | --- | --- |
| `challenge_search` | topic words | Britannica entries with their match decision and a text snippet |
| `challenge_compare` | `entry_id` | source record, OCR text, Wikipedia match with scores and reason, vocabulary comparison, checked fact claims, evidence rules |
| `challenge_passages` | Wikipedia `page_id`, query | passages from the saved article text with their offsets |
| `challenge_scan` | `entry_id` | scan path, checksum, entry box, and an enlarged crop of the entry |
| `challenge_corpus` | none | match counts, distinctive words, topic clusters, spelling changes |

Each result names its sources.
Britannica sources have the page ID, scan checksum, and block IDs.
Wikipedia sources have the page ID, revision ID, and text checksum.
A tool returns an error object instead of raising.

`challenge_compare` returns these evidence rules to the model:

1. Answer only from tool results, and cite every source by its IDs.
2. Quote a fact claim only when both `quote_found` flags are true.
3. An `uncertain` or `no_match` decision is not evidence that two sources describe the same topic.
4. When no saved entry or article covers the question, say that the evidence is missing.
5. Check doubtful OCR words against the scan with `challenge_scan` and the vision tool.
6. Ask the vision tool for a transcription. Do not give it the OCR reading.

## Run the agent stage

```bash
uv run nemotron-challenge run agent
```

The stage does these steps:

1. It builds `artifacts/agent/index.json` and the entry crops in `artifacts/agent/crops/`.
2. It copies the plugin from the repository into `data/hermes/plugins`, so each run uses the committed tool code.
3. It asks the six questions in `agent.QUESTIONS`, each in a new one-shot session.

Each question runs this command:

```bash
hermes chat --oneshot -t nemotron_challenge,vision --format stream-json \
  --max-turns 12 --run-budget 600 --source tool -q "<question>"
```

The `vision` toolset adds `vision_analyze`.
With Super VL as the main model, `vision_analyze` loads the image into the model's own context.

## Run records

Each run writes `artifacts/agent/runs/<question>-<UTC time>.json`.
The record has the question, the Hermes version, the command, the exit code, the model ID, each tool call with its input and output, the final answer, token counts, and the raw stream-json output.

The stream-json output keeps about 5,000 characters of each tool result.
The full result stays in `data/hermes/state.db` under the run's `session_id`.
The index is built from committed artifacts, so you can also rebuild a tool result from them.

Keep failed runs.
Write a repaired run to a new record.
`evaluation/review.json` links a failed run to its repair with `repaired_by`.

## Vision checks

The first runs gave `vision_analyze` the full page and a pixel `region`.
Hermes crops the region but does not enlarge it.
The model then got images from 30 to 187 pixels high and misread the long s.
When the question offered the OCR reading as an option, the model chose an option instead of reading the print.

We tested Super VL directly on the sword entry, with a neutral question.
The receipts are in `evaluation/vision_check.json`.
At page resolution it read "ſlab". At 4x it read "ſtab", which is correct.

Now `challenge_scan` returns `crop_path`, the entry region enlarged up to 4 times with LANCZOS.
The long side of a crop is not more than 2,400 pixels.
Hermes passes the crop to the model as a JPEG of the same size.

This repair corrected the steam engine case.
It did not correct the sword case.
In that run the model said the image was too blurry, then reported the word from a fact claim in its context.
See cases F1 and F3 in `evaluation/review.json`.

## Check registration

```bash
hermes plugins doctor integrations/hermes/nemotron-challenge --ci
hermes plugins list
uv run pytest tests/test_agent.py
```

Plugin Doctor checks discovery, imports, and registration.
The tests check the index, every tool on a small saved project, and the crop size.
Neither check calls a model.
