
# mbq_parser.py — clean refactor (v2, Comfy-based)
# ---------------------------------------------------------------------
# Uses ComfyUI's own input-graph logic via comfy_exec_core.py
# to extract model, prompt, and sampler data from PNG tEXt chunks.
# ---------------------------------------------------------------------
# Copyright © 2025 Beak11
# Portions derived from ComfyUI (GPL-3.0)
# ---------------------------------------------------------------------

from __future__ import annotations
import json, struct, time
from pathlib import Path
from typing import Optional
from mbq_metadata import ImageMetadata
from mbq_nodes import parse_nodes, NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS


# ---------------------------------------------------------------------
# In-memory cache
# ---------------------------------------------------------------------
_CACHE: dict[str, ImageMetadata] = {}
_CACHE_MAX = 20

def _cache_get(path) -> Optional[ImageMetadata]:
    return _CACHE.get(str(path))

def _cache_put(path, blob: ImageMetadata):
    k = str(path)
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[k] = blob



# ---------------------------------------------------------------------
# PNG tEXt JSON extractor (prompt + workflow)
# ---------------------------------------------------------------------
def extract_json_chunks(file_path: Path):
    """Return (prompt_json, workflow_json) from PNG metadata."""
    prompt_json = workflow_json = None
    with open(file_path, "rb") as f:
        if f.read(8) != b"\x89PNG\r\n\x1a\n":
            return None, None
        while True:
            length_bytes = f.read(4)
            if not length_bytes:
                break
            length = struct.unpack(">I", length_bytes)[0]
            ctype = f.read(4).decode("ascii", "ignore")
            data = f.read(length)
            f.read(4)  # skip CRC
            if ctype == "tEXt":
                key, _, txt = data.partition(b"\x00")
                key = key.decode("latin-1", "ignore")
                val = txt.decode("latin-1", "ignore")
                try:
                    js = json.loads(val)
                except json.JSONDecodeError:
                    js = None
                if key == "prompt":
                    prompt_json = js
                elif key == "workflow":
                    workflow_json = js
            if ctype == "IEND":
                break
    return prompt_json, workflow_json


# ---------------------------------------------------------------------
# Main workflow digester
# ---------------------------------------------------------------------
# mbq_parser.py (simplified core)

def digest_workflow(file_path: str | Path) -> ImageMetadata:
    path = Path(file_path)
    if cached := _cache_get(path):
        return cached

    blob = ImageMetadata(file=path)

    prompt_json, workflow_json = extract_json_chunks(path)
    if not prompt_json and not workflow_json:
        print(f"[parser] ⚠️ No genAI metadata in {path.name}")
        blob.parsed_ok = False
        _cache_put(path, blob)
        return blob

    # parse nodes via mbq_nodes
    core, extra, summary = parse_nodes(workflow_json or prompt_json)

    # populate core fields
    blob.model = summary.get("model")
    blob.prompt = summary.get("prompt")
    blob.negative_prompt = summary.get("negative_prompt")
    blob.sampler = summary.get("sampler")
    blob.scheduler = summary.get("scheduler")
    blob.steps = summary.get("steps")
    blob.cfg = summary.get("cfg")
    blob.seed = summary.get("seed")
    blob.denoise = summary.get("denoise")

    # add diagnostics
    blob.core_nodes = core
    blob.third_party_nodes = extra
    blob.has_third_party = bool(extra)
    blob.parsed_ok = True
    _cache_put(path, blob)
    return blob


# ---------------------------------------------------------------------
# CLI test harness
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# CLI test harness
# ---------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python mbq_parser.py <file.png>")
        sys.exit(1)

    target = Path(sys.argv[1])
    prompt_json, workflow_json = extract_json_chunks(target)

    print(f"\n=== {target.name} ===")
    if workflow_json:
        #print("\nlinks list: " + json.dumps(workflow_json["links"], indent=2)[:1000])
        print(f"Workflow keys: {list(workflow_json.keys())}")
        print(f"Nodes: {len(workflow_json.get('nodes', []))}")
        print("Example node:")
        if workflow_json.get("nodes"):
            print(json.dumps(workflow_json["nodes"][0], indent=2)[:800])
        else:
            print("(no nodes found)")
    elif prompt_json:
        print("No workflow found, but prompt JSON present.")
        print(json.dumps(prompt_json, indent=2)[:800])
    else:
        print("No JSON metadata found.")

