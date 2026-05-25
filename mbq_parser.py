from __future__ import annotations
import json
import struct
import zlib
from pathlib import Path
from typing import Optional, Any

from mbq_metadata import ImageMetadata

_CACHE: dict[str, ImageMetadata] = {}
_CACHE_MAX = 20


def _cache_get(path) -> Optional[ImageMetadata]:
    return _CACHE.get(str(path))


def _cache_put(path, blob: ImageMetadata):
    k = str(path)
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[k] = blob


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
            ctype = f.read(4)
            data = f.read(length)
            f.read(4)

            key = None
            txt = None

            if ctype == b"tEXt":
                key, _, raw = data.partition(b"\x00")
                key = key.decode("latin-1", "ignore")
                txt = raw.decode("utf-8", "ignore")

            elif ctype == b"zTXt":
                key, _, rest = data.partition(b"\x00")
                key = key.decode("latin-1", "ignore")
                try:
                    txt = zlib.decompress(rest[1:]).decode("utf-8", "ignore")
                except Exception:
                    txt = None

            elif ctype == b"iTXt":
                key, _, rest = data.partition(b"\x00")
                key = key.decode("latin-1", "ignore")
                try:
                    if len(rest) >= 2:
                        comp_flag = rest[0]
                        payload = rest[2:]
                        parts = payload.split(b"\x00", 2)
                        txt_bytes = parts[2] if len(parts) == 3 else payload
                        if comp_flag:
                            txt_bytes = zlib.decompress(txt_bytes)
                        txt = txt_bytes.decode("utf-8", "ignore")
                except Exception:
                    txt = None

            if key in ("prompt", "workflow") and txt:
                try:
                    js = json.loads(txt)
                except json.JSONDecodeError:
                    js = None
                if key == "prompt":
                    prompt_json = js
                elif key == "workflow":
                    workflow_json = js

            if ctype == b"IEND":
                break

    return prompt_json, workflow_json


def _normalized_alnum(text: str) -> str:
    return "".join(ch.lower() for ch in str(text) if ch.isalnum())


def _prefix_basename(prefix: str) -> str:
    return Path(str(prefix).replace("\\", "/")).name


def _basename_matches_stem(stem: str, prefix: str) -> bool:
    stem_norm = _normalized_alnum(stem)
    prefix_norm = _normalized_alnum(_prefix_basename(prefix))
    return bool(stem_norm and prefix_norm and stem_norm.startswith(prefix_norm))


def _prompt_nodes(prompt_json: Any) -> dict[str, dict]:
    return prompt_json if isinstance(prompt_json, dict) else {}


def _workflow_nodes(workflow_json: Any) -> list[dict]:
    if isinstance(workflow_json, dict):
        nodes = workflow_json.get("nodes")
        if isinstance(nodes, list):
            return nodes
    return []


def _class_type_from_prompt_node(node: dict) -> str:
    return str(node.get("class_type") or "")


def _class_type_from_workflow_node(node: dict) -> str:
    return str(node.get("type") or "")


def _workflow_widget_value(node: dict, index: int, default=None):
    vals = node.get("widgets_values")
    if isinstance(vals, list) and index < len(vals):
        return vals[index]
    return default


def _extract_saveimage_candidates(prompt_json: Any, workflow_json: Any) -> list[dict]:
    candidates = []

    for node_id, node in _prompt_nodes(prompt_json).items():
        if _class_type_from_prompt_node(node).lower() == "saveimage":
            prefix = node.get("inputs", {}).get("filename_prefix")
            if prefix:
                candidates.append({
                    "source": "prompt",
                    "node_id": str(node_id),
                    "prefix": str(prefix),
                    "node": node,
                })

    for node in _workflow_nodes(workflow_json):
        if _class_type_from_workflow_node(node).lower() == "saveimage":
            prefix = _workflow_widget_value(node, 0)
            if prefix:
                candidates.append({
                    "source": "workflow",
                    "node_id": str(node.get("id")),
                    "prefix": str(prefix),
                    "node": node,
                })

    return candidates


def _find_matching_saveimage(path: Path, prompt_json: Any, workflow_json: Any):
    candidates = _extract_saveimage_candidates(prompt_json, workflow_json)
    if not candidates:
        return None, []

    matches = [c for c in candidates if _basename_matches_stem(path.stem, c["prefix"])]
    if not matches:
        return None, candidates

    prompt_matches = [m for m in matches if m["source"] == "prompt"]
    chosen_pool = prompt_matches or matches

    unique_by_base = {}
    for item in chosen_pool:
        base = _normalized_alnum(_prefix_basename(item["prefix"]))
        unique_by_base.setdefault(base, item)

    unique_matches = list(unique_by_base.values())
    if len(unique_matches) == 1:
        return unique_matches[0], candidates

    return {"ambiguous_matches": unique_matches}, candidates


def _extract_node_refs(value) -> list[str]:
    refs = []
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, (str, int)):
            refs.append(str(first))
    return refs


def _trace_upstream_prompt_nodes(prompt_json: Any, start_node_id: str) -> set[str]:
    nodes = _prompt_nodes(prompt_json)
    if start_node_id not in nodes:
        return set()

    seen = set()
    stack = [start_node_id]

    while stack:
        node_id = stack.pop()
        if node_id in seen:
            continue
        seen.add(node_id)
        node = nodes.get(node_id, {})
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue
        for value in inputs.values():
            for ref in _extract_node_refs(value):
                if ref in nodes and ref not in seen:
                    stack.append(ref)

    return seen


def _reachable_prompt_nodes(prompt_json: Any, node_ids: set[str]) -> list[tuple[str, dict]]:
    nodes = _prompt_nodes(prompt_json)
    out = []
    for node_id in node_ids:
        node = nodes.get(node_id)
        if isinstance(node, dict):
            out.append((str(node_id), node))
    return out


def _find_best_sampler_inputs(reachable_nodes: list[tuple[str, dict]]) -> dict:
    candidate_nodes = []
    for node_id, node in reachable_nodes:
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue

        score = sum(1 for key in ("seed", "steps", "cfg", "sampler_name", "scheduler", "denoise") if key in inputs)
        ctype = _class_type_from_prompt_node(node)
        if ctype == "KSampler":
            score += 20
        elif ctype in ("UltimateSDUpscale", "UltimateSDUpscaleCustomSample", "SamplerCustomAdvanced"):
            score += 10

        if score:
            candidate_nodes.append((score, node_id, node))

    if not candidate_nodes:
        return {}

    candidate_nodes.sort(key=lambda item: item[0], reverse=True)
    best_node = candidate_nodes[0][2]
    merged = dict(best_node.get("inputs", {}))

    if "sampler_name" not in merged or "scheduler" not in merged or "steps" not in merged:
        for _, node in reachable_nodes:
            inputs = node.get("inputs", {})
            if "sampler_name" in inputs and "sampler_name" not in merged:
                merged["sampler_name"] = inputs["sampler_name"]
            if "scheduler" in inputs and "scheduler" not in merged:
                merged["scheduler"] = inputs["scheduler"]
            if "steps" in inputs and "steps" not in merged:
                merged["steps"] = inputs["steps"]

    if "seed" not in merged:
        for _, node in reachable_nodes:
            inputs = node.get("inputs", {})
            if "noise_seed" in inputs:
                merged["seed"] = inputs["noise_seed"]
                break

    if "guidance" not in merged:
        for _, node in reachable_nodes:
            inputs = node.get("inputs", {})
            if "guidance" in inputs:
                merged["guidance"] = inputs["guidance"]
                break

    return merged


def _clean_text(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _extract_prompts(reachable_nodes: list[tuple[str, dict]]) -> tuple[Optional[str], Optional[str]]:
    positive = []
    negative = []

    for _, node in reachable_nodes:
        ctype = _class_type_from_prompt_node(node).lower()
        if "cliptextencode" not in ctype:
            continue

        inputs = node.get("inputs", {})
        meta = node.get("_meta", {}) if isinstance(node.get("_meta"), dict) else {}
        title = str(meta.get("title", "")).lower()

        text_candidates = []
        for key in ("text", "t5xxl", "clip_l"):
            val = _clean_text(inputs.get(key))
            if val:
                text_candidates.append(val)

        if not text_candidates:
            continue

        combined = "\n".join(text_candidates).strip()
        if not combined:
            continue

        looks_negative = ("negative" in title) or ("neg" in title and "positive" not in title)
        if looks_negative:
            negative.append(combined)
        else:
            positive.append(combined)

    def pick_best(values):
        unique = []
        seen = set()
        for v in values:
            if v not in seen:
                seen.add(v)
                unique.append(v)
        unique.sort(key=len, reverse=True)
        return unique[0] if unique else None

    return pick_best(positive), pick_best(negative)


def _extract_model_name(reachable_nodes: list[tuple[str, dict]]) -> Optional[str]:
    for _, node in reachable_nodes:
        inputs = node.get("inputs", {})
        for key in ("ckpt_name", "unet_name", "model_name"):
            val = _clean_text(inputs.get(key))
            if val:
                return val
    return None


def _extract_controlnets(reachable_nodes: list[tuple[str, dict]]) -> list[str]:
    found = []
    for _, node in reachable_nodes:
        inputs = node.get("inputs", {})
        val = _clean_text(inputs.get("control_net_name"))
        if val and val not in found:
            found.append(val)
    return found


def _safe_int(value):
    try:
        return int(value)
    except Exception:
        return None


def _safe_float(value):
    try:
        return float(value)
    except Exception:
        return None


def _populate_summary_from_prompt(blob: ImageMetadata, prompt_json: Any, matched_node_id: str):
    reachable_ids = _trace_upstream_prompt_nodes(prompt_json, matched_node_id)
    reachable_nodes = _reachable_prompt_nodes(prompt_json, reachable_ids)
    blob.nodes = [f"{node_id}:{_class_type_from_prompt_node(node)}" for node_id, node in sorted(reachable_nodes, key=lambda x: x[0])]

    sampler_inputs = _find_best_sampler_inputs(reachable_nodes)
    blob.model = _extract_model_name(reachable_nodes)
    blob.controlnets = _extract_controlnets(reachable_nodes)
    blob.prompt, blob.negative_prompt = _extract_prompts(reachable_nodes)
    blob.seed = _safe_int(sampler_inputs.get("seed"))
    blob.steps = _safe_int(sampler_inputs.get("steps"))
    blob.cfg = _safe_float(sampler_inputs.get("cfg"))
    blob.guidance = _safe_float(sampler_inputs.get("guidance"))
    blob.denoise = _safe_float(sampler_inputs.get("denoise"))
    blob.sampler = _clean_text(sampler_inputs.get("sampler_name"))
    blob.scheduler = _clean_text(sampler_inputs.get("scheduler"))


def digest_workflow(file_path: str | Path) -> ImageMetadata:
    path = Path(file_path)
    if cached := _cache_get(path):
        return cached

    blob = ImageMetadata(file=path)

    try:
        prompt_json, workflow_json = extract_json_chunks(path)
    except Exception as e:
        blob.parsed_ok = False
        blob.error_message = str(e)
        blob.trust_status = "error"
        blob.ambiguity_reason = f"Metadata parse failed: {e}"
        _cache_put(path, blob)
        return blob

    if not prompt_json and not workflow_json:
        blob.parsed_ok = False
        blob.trust_status = "no_md"
        blob.ambiguity_reason = "No metadata found."
        _cache_put(path, blob)
        return blob

    blob.raw_json = prompt_json or workflow_json
    blob.workflow_type = "ComfyUI"

    matched, candidates = _find_matching_saveimage(path, prompt_json, workflow_json)
    blob.saveimage_prefixes = [c["prefix"] for c in candidates]

    if not candidates:
        blob.parsed_ok = False
        blob.trust_status = "pass"
        blob.ambiguity_reason = "No SaveImage prefix found; confusing, pass."
        _cache_put(path, blob)
        return blob

    if matched is None:
        blob.parsed_ok = False
        blob.trust_status = "pass"
        blob.ambiguity_reason = "Filename and SaveImage basename do not match; confusing, pass."
        _cache_put(path, blob)
        return blob

    if "ambiguous_matches" in matched:
        bases = sorted({_prefix_basename(m["prefix"]) for m in matched["ambiguous_matches"]})
        blob.parsed_ok = False
        blob.trust_status = "confusing"
        blob.ambiguity_reason = f"Multiple SaveImage basename matches ({', '.join(bases)}); confusing, pass."
        _cache_put(path, blob)
        return blob

    blob.matched_saveimage_prefix = matched["prefix"]
    blob.matched_saveimage_node_id = matched["node_id"]

    if prompt_json and matched["source"] == "prompt":
        _populate_summary_from_prompt(blob, prompt_json, matched["node_id"])

    blob.trusted_workflow = True
    blob.trust_status = "trusted"
    blob.parsed_ok = True

    _cache_put(path, blob)
    return blob


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python mbq_parser.py <file.png>")
        raise SystemExit(1)

    target = Path(sys.argv[1])
    md = digest_workflow(target)
    print(json.dumps(md.as_dict(), indent=2, default=str))
