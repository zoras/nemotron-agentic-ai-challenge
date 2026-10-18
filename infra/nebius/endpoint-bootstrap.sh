#!/usr/bin/env bash
# Start the retrieval model service on the public PyTorch base image without a custom image build.
#
# A Nebius Serverless endpoint injects this file and runs it with bash. It fetches the service files
# from one pinned commit and checks their SHA-256 hashes, installs the hashed package lock, downloads
# the pinned model snapshots, and starts the uvicorn command from infra/model-service/Dockerfile.
# Each cold start repeats the downloads, because an endpoint loses its container disk when it stops.
set -euo pipefail

COMMIT=baaeb0cbf6b20e21ea1517ea60bda8b2d6392077
SOURCE=https://raw.githubusercontent.com/prabeshsb/nemotron-agentic-ai-challenge/$COMMIT/infra/model-service

export PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 \
  HF_HUB_DISABLE_IMPLICIT_TOKEN=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1

mkdir -p /service
cd /service
python - "$SOURCE" <<'PY'
import hashlib
import sys
import urllib.request

FILES = {
    "requirements.lock": "74d4df897f89c81c9ffd9126d577891b61107c0fa54f5f8e5d93bf49badd3e79",
    "app.py": "9112719813b04cf9a7cd211f4d45007c09819709fffc5330a95191669339033c",
    "backend.py": "5b4c14b31c068a6f8590f214db911765bf66aa5b3c58f9d93d1b0e725d76d9d0",
    "contracts.py": "7794d1949910f669bd1973d07a34791e1b5eb13f77e3996f7cec641d8af5ee29",
    "model_pins.py": "3f40b4a7662285596aef47710727ff8775718f65daf0b8bf7bf24969c452fe73",
    "download_models.py": "30248fd6f76d1e62359079c647c124b58ea58c3c95b3f9eb7c42c34922550967",
    "NOTICE.md": "78383d69093f6342cf2b8a8e0afdbb24d1a47bf4985ade7ba87a3aebadf06ae1",
}
for name, expected in FILES.items():
    data = urllib.request.urlopen(f"{sys.argv[1]}/{name}", timeout=60).read()
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        sys.exit(f"{name}: SHA-256 {actual} differs from the pinned {expected}")
    with open(name, "wb") as stream:
        stream.write(data)
    print(f"fetched {name} {actual}", flush=True)
PY

python -m pip install --require-hashes --only-binary=:all: -r requirements.lock
python -c "import torch, torchvision, transformers; assert torch.__version__.split('+')[0] == '2.8.0'; assert torch.version.cuda == '12.8'; assert torchvision.__version__.split('+')[0] == '0.23.0'; assert transformers.__version__ == '4.56.2'; assert 'sm_120' in torch._C._cuda_getArchFlags().split(); print('CUDA package and sm_120 build checks passed', flush=True)"
python download_models.py --destination /opt/models

export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HOME=/tmp/huggingface \
  HF_MODULES_CACHE=/tmp/huggingface/modules MODEL_ROOT=/opt/models
exec python -m uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1 --limit-concurrency 16 --timeout-keep-alive 5
