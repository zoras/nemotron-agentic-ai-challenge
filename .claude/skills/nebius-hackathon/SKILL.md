---
name: nebius-hackathon
description: Event rules for this team's Nebius environment. Use with the nebius-cloud plugin skills for any Nebius AI Cloud, GPU, endpoint, devlab, job, VM, Object Storage bucket, SecretStash, or Token Factory task in this repository, such as deploying the embedder and reranker or setting RETRIEVAL_BASE_URL.
---

# Nebius hackathon environment

Use this skill together with the `nebius-cloud` plugin skills.
The plugin skills give general Nebius CLI steps.
This skill gives the event limits and the rules that apply to this repository.
If a plugin skill conflicts with this skill, follow this skill.

The full event guide is in [references/participant-guide.md](references/participant-guide.md).
Read its sections 4, 5, and 10 before you create or diagnose a workload.
Do not repeat the plugin installation in guide section 11, Step 2.
`.claude/settings.json` already enables the `nebius-cloud` plugin for this project.

## Scope

- Use the tenant named in the invitation email.
- Use only the team's assigned project in that tenant.
- Use region `uk-south2`.
- Ask the team for the project ID. Do not infer it from the example name `group01-project`.
- Do not create a personal tenant. Do not switch region or project to work around an error.
- Use the team's CLI profile from `nebius profile create`. The guide uses the profile name `hackathon`.

## Team limits

All team members and workloads share these limits.

| Resource | Limit |
| --- | --- |
| Reserved GPU | 1 NVIDIA RTX PRO 6000 Blackwell Server Edition |
| GPU platform and preset | `gpu-rtx6000-a` and `1gpu-24vcpu-218gb` |
| VMs | 3, including VMs that Serverless workloads use |
| vCPUs for non-GPU VMs | 20 |
| Disks | 4 |
| Network SSD disk capacity | 500 GiB, including container and boot disks |
| Public IPv4 addresses | 1 |
| Container registries | 1 |
| Object Storage buckets | 1 Standard bucket, size limit 200 GiB |

A GPU endpoint and a GPU devlab cannot run at the same time.
When the GPU endpoint runs, select **Without GPUs** for a devlab and set a CPU preset.
Some templates request a GPU by default.

## Rules that override the plugin skills

- Do not create a service account or generate an access key. The `nebius-serverless-setup` skill does this. The event supplies Object Storage keys in the SecretStash entry `hackathon-object-storage`.
- Do not change permissions. Ask an organizer when access fails.
- Do not show credential values in chat, logs, notebooks, or Git. The CLI service name for SecretStash is `mysterybox`.
- List the project's running workloads before you create one. Ask the team which workloads they use.
- Run each create command with `--dry-run` first. Show the full command with secret references. State the resource use and cost.
- Get explicit confirmation for each deployment. Approval of setup does not approve a create.
- Do not delete a workload. Print the command for a team member to run.

## What this repository needs

| Service | Where it runs | Settings in `.env` |
| --- | --- | --- |
| Parse 3.5 | Organizer endpoint | `PARSE_BASE_URL` |
| Wikipedia API | Organizer endpoint | `WIKIPEDIA_API_URL` |
| Embedder and reranker | Team GPU, as a Serverless endpoint or a GPU VM | `RETRIEVAL_BASE_URL`, `RETRIEVAL_API_KEY` |
| Super 3.5 VL | Nebius Token Factory | `SUPER_BASE_URL`, `SUPER_API_KEY` |

### Embedder and reranker

- Build or obtain the image as [docs/model-service.md](../../../docs/model-service.md) describes. The image is `linux/amd64` and listens on port 8000.
- Use the organizer image, or push your image to the team's container registry.
- Use the GPU preset above. The reference hardware in `docs/model-service.md` is the same GPU.
- For a Serverless endpoint, turn on bearer token authentication. Put the endpoint URL plus `/v1` in `RETRIEVAL_BASE_URL`. Put the endpoint token in `RETRIEVAL_API_KEY`. The client sends that value as `Authorization: Bearer`.
- The image contains the model weights, but a cold start still pulls the image and loads the models. Expect `503` until `/ready` returns `200`.
- Run `infra/model-service/smoke_gpu.py` against the endpoint. Keep the receipt in `runs/`.
- Record the endpoint ID, image digest, and smoke receipt. Record failed runs with their error details.

### Super 3.5 VL

- Token Factory has its own account, credits, and API key. Cloud access does not give Token Factory access.
- The base URL is `https://api.tokenfactory.nebius.com/v1`. This repository reads the key from `SUPER_API_KEY`. The Token Factory quickstart uses `NEBIUS_API_KEY` for the same key.

### Object Storage

- Use the bucket only if the team needs durable files, such as model outputs or run receipts.
- Reuse the team bucket if a teammate made it.
- Set the S3 endpoint `https://storage.uk-south2.nebius.cloud` in each client.

## Save work and release the GPU

- A stopped or deleted endpoint loses its container disk. Save outputs first.
- A stopped devlab keeps its disk and uses disk capacity.
- After you stop a workload, check that the GPU and disk capacity are free before you start the next one.

## CLI requirements

- The Serverless and devlab skills need `nebius` CLI 0.12.277 or later.
- Ask a team member to install or update the CLI. Do not run the installer yourself.

## Sources

- Event guide: `dariolaportanebius/nebius-starter-skill` at commit `81769dde5ee14f8ef831f0db048b1f71372a977a`. Copyright 2026 Anton Smith, MIT license, in [references/participant-guide-LICENSE.txt](references/participant-guide-LICENSE.txt).
- Plugin skills: `nebius/skills` plugin `nebius-cloud` 0.1.0, checked at commit `2db737976de0f760d701b16a891f0273309a4744`. Apache 2.0 license.
