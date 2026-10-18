"""Ask Super VL to read one scan crop at page resolution and at 4x. Save the raw replies as receipts.

Run from the repository root: uv run python evaluation/vision_check.py evaluation/vision_check.json
"""
import base64, hashlib, io, json, sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from nemotron_challenge.clients import ChatClient
from nemotron_challenge.config import Settings

CASES = [
    {"case": "sword", "filename": "page-0251-69952e7c4a0f.jpg", "box": [298, 211, 563, 398],
     "question": "Transcribe the first two printed lines of the SWORD entry in this image exactly, letter by letter. "
                 "Write a long s as ſ. Then give the last word of the first sentence as printed."},
    {"case": "steam", "filename": "page-0523-a583606e375a.jpg", "box": [298, 50, 552, 145],
     "question": "Transcribe the lines about Steam-ENGINE in this image exactly, letter by letter. "
                 "Write a long s as ſ. Then give the word printed after 'turned into'."},
]
SCALES = (1, 4)


def data_url(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


settings = Settings.from_env()
receipts = []
with ChatClient(settings.super_base_url, settings.super_api_key, settings.super_model) as chat:
    for case in CASES:
        path = Path("data/raw/britannica") / case["filename"]
        page = Image.open(path).convert("RGB")
        crop = page.crop(tuple(case["box"]))
        for scale in SCALES:
            image = crop if scale == 1 else crop.resize((crop.width * scale, crop.height * scale), Image.Resampling.LANCZOS)
            row = {"case": case["case"], "filename": case["filename"],
                   "image_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "box_px": case["box"],
                   "scale": scale, "sent_size": list(image.size), "question": case["question"],
                   "requested_model": settings.super_model,
                   "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            try:
                reply = chat.complete([{"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": data_url(image)}},
                    {"type": "text", "text": case["question"]}]}], max_tokens=4096)
                choice = reply["choices"][0]
                row.update({"model": reply.get("model"), "finish_reason": choice.get("finish_reason"),
                            "content": choice["message"]["content"], "usage": reply.get("usage")})
            except Exception as error:  # record the failed call with its error details
                row.update({"error": f"{type(error).__name__}: {error}"})
            receipts.append(row)
            print(json.dumps({k: row.get(k) for k in ("case", "scale", "sent_size", "model", "finish_reason", "error")}))

out = Path(sys.argv[1])
out.write_text(json.dumps({"script": "evaluation/vision_check.py", "purpose": "Check whether Super VL reads small scan crops better after upscaling. "
                                      "Raw model replies; not edited.", "receipts": receipts},
                          ensure_ascii=False, indent=1), encoding="utf-8")
print("saved", out)
