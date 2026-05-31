from __future__ import annotations
import json
import struct
import zlib
from pathlib import Path
from typing import Optional

_CACHE: dict[str, dict] = {}
_CACHE_MAX = 20

_SUPPRESS = {"SaveImage", "Note", "PrimitiveNode"}

_SAMPLER_KEYS = {
    "steps", "cfg", "seed", "noise_seed", "sampler_name",
    "scheduler", "guidance", "denoise",
}

_MODEL_EXTS = {".safetensors", ".ckpt", ".pt", ".gguf", ".bin", ".pth"}


def _cache_get(path) -> Optional[dict]:
    return _CACHE.get(str(path))


def _cache_put(path, data: dict):
    k = str(path)
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[k] = data


def _read_png_text_chunks(file_path: Path, want: set[str]) -> dict[str, str]:
    """Scan a PNG once and return raw text values for the requested chunk keys."""
    found: dict[str, str] = {}
    try:
        with open(file_path, "rb") as f:
            if f.read(8) != b"\x89PNG\r\n\x1a\n":
                return found
            while True:
                length_bytes = f.read(4)
                if not length_bytes:
                    break
                length = struct.unpack(">I", length_bytes)[0]
                ctype  = f.read(4)
                data   = f.read(length)
                f.read(4)                       # CRC

                key = txt = None
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
                        pass
                elif ctype == b"iTXt":
                    key, _, rest = data.partition(b"\x00")
                    key = key.decode("latin-1", "ignore")
                    try:
                        if len(rest) >= 2:
                            comp_flag = rest[0]
                            payload   = rest[2:]
                            parts     = payload.split(b"\x00", 2)
                            txt_bytes = parts[2] if len(parts) == 3 else payload
                            if comp_flag:
                                txt_bytes = zlib.decompress(txt_bytes)
                            txt = txt_bytes.decode("utf-8", "ignore")
                    except Exception:
                        pass

                if key in want and txt:
                    found[key] = txt
                    if found.keys() == want:
                        break           # got everything we need early

                if ctype == b"IEND":
                    break
    except Exception:
        pass
    return found


def read_prompt_chunk(file_path: Path) -> Optional[dict]:
    """Extract the 'prompt' JSON from a PNG's text chunks. Returns None if absent."""
    chunks = _read_png_text_chunks(file_path, {"prompt"})
    txt = chunks.get("prompt")
    if txt:
        try:
            return json.loads(txt)
        except json.JSONDecodeError:
            pass
    return None


def _is_wire(v) -> bool:
    """A node-reference wire: [str_node_id, int_slot]. Skip these — they carry no value."""
    return isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and isinstance(v[1], int)


def _scalar_inputs(inputs: dict) -> dict:
    """Return only the scalar (non-wire) inputs."""
    return {k: v for k, v in inputs.items() if not _is_wire(v) and v is not None}


def _node_tier(class_type: str, params: dict) -> int:
    """Classify a node 1/2/3 based on what its scalar inputs contain, not its name."""
    if class_type in _SUPPRESS:
        return 3
    if not params:
        return 3
    for k, v in params.items():
        if k in _SAMPLER_KEYS:
            return 1
        if isinstance(v, str):
            if any(v.endswith(e) for e in _MODEL_EXTS):
                return 1
            if len(v) > 30:
                return 1
    return 2


def _split_sampler(entries: list) -> list:
    """Nodes mixing sampler-key params with content params → two entries."""
    out = []
    for e in entries:
        sam = {k: v for k, v in e["params"].items() if k in _SAMPLER_KEYS}
        other = {k: v for k, v in e["params"].items() if k not in _SAMPLER_KEYS}
        if sam and other:
            out.append({**e, "params": other})
            out.append({**e, "params": sam})
        else:
            out.append(e)
    return out


def _display_priority(params: dict) -> int:
    """Sub-sort key within tier 1: model loaders first, then prompts, then sampler config."""
    for v in params.values():
        if isinstance(v, str) and any(v.endswith(e) for e in _MODEL_EXTS):
            return 1
    for v in params.values():
        if isinstance(v, str) and len(v) > 30:
            return 2
    for k in params:
        if k in _SAMPLER_KEYS:
            return 3
    return 4


def _dedup(nodes: list) -> list:
    seen: set = set()
    out: list = []
    for entry in nodes:
        key = entry["class_type"] + json.dumps(entry["params"], sort_keys=True, default=str)
        if key not in seen:
            seen.add(key)
            out.append(entry)
    return out


def tier_prompt_nodes(prompt_json: dict) -> tuple[list, list, list]:
    """Return (tier1, tier2, tier3). Each entry: {class_type, title, params}."""
    t1: list = []
    t2: list = []
    t3: list = []
    for node in prompt_json.values():
        if not isinstance(node, dict):
            continue
        ctype = str(node.get("class_type") or "")
        title = str((node.get("_meta") or {}).get("title", ""))
        params = _scalar_inputs(node.get("inputs") or {})
        entry = {"class_type": ctype, "title": title, "params": params}
        tier = _node_tier(ctype, params)
        [t1, t2, t3][tier - 1].append(entry)
    t1 = _split_sampler(t1)
    t1.sort(key=lambda e: (_display_priority(e["params"]), e["class_type"]))
    t2.sort(key=lambda e: e["class_type"])
    t3.sort(key=lambda e: e["class_type"])
    return _dedup(t1), _dedup(t2), _dedup(t3)


def _saveimage_prefixes(prompt_json: dict) -> list:
    """Return filename_prefix strings from all SaveImage nodes (skip wired values)."""
    prefixes = []
    for node in prompt_json.values():
        if not isinstance(node, dict):
            continue
        if node.get("class_type") == "SaveImage":
            v = (node.get("inputs") or {}).get("filename_prefix")
            if v and isinstance(v, str) and not _is_wire(v):
                prefixes.append(v)
    return prefixes


def get_wedge_data(prompt_json: dict) -> Optional[dict]:
    """Return wedge info if an MBQWedge node is wired to a real parameter, else None.

    Connection is determined by checking whether any other node in the prompt has
    an input named `parameter_name` wired to the wedge node — the same wire that
    makes the sweep meaningful. A wedge that is present but not connected (or only
    connected to display/preview nodes) is silently ignored so the viewer stays clean.
    The prompt JSON is never modified; this is read-only display logic.
    """
    wedge_id     = None
    wedge_params = None

    for nid, node in prompt_json.items():
        if isinstance(node, dict) and node.get("class_type") == "MBQWedge":
            wedge_id     = nid
            wedge_params = _scalar_inputs(node.get("inputs") or {})
            break

    if wedge_params is None:
        return None

    param_name = wedge_params.get("parameter_name", "")
    if not param_name:
        return None

    # Check that some downstream node has an input whose NAME matches parameter_name
    # and whose value is a wire reference [wedge_id, slot].
    connected = any(
        key == param_name
        and isinstance(v, list) and len(v) >= 1
        and str(v[0]) == wedge_id
        for nid, node in prompt_json.items()
        if nid != wedge_id and isinstance(node, dict)
        for key, v in (node.get("inputs") or {}).items()
    )
    if not connected:
        return None

    return {
        "parameter_name": param_name,
        "current_value":  wedge_params.get("current"),
        "start":          wedge_params.get("start"),
        "increment":      wedge_params.get("increment"),
        "stop":           wedge_params.get("stop"),
    }


def get_png_metadata(file_path: str | Path) -> dict:
    """Return parsed metadata dict or {} if no prompt chunk."""
    path = Path(file_path)
    if (cached := _cache_get(path)) is not None:
        return cached
    chunks = _read_png_text_chunks(path, {"prompt", "workflow"})
    prompt_txt = chunks.get("prompt")
    prompt_json = None
    if prompt_txt:
        try:
            prompt_json = json.loads(prompt_txt)
        except json.JSONDecodeError:
            pass
    if prompt_json is not None:
        result = {
            "tiers":              tier_prompt_nodes(prompt_json),
            "saveimage_prefixes": _saveimage_prefixes(prompt_json),
            "wedge":              get_wedge_data(prompt_json),
            "raw_prompt":         prompt_json,
            "raw_workflow":       chunks.get("workflow"),   # LiteGraph JSON string, or None
        }
    else:
        result = {}
    _cache_put(path, result)
    return result


if __name__ == "__main__":
    import sys
    import pprint
    if len(sys.argv) < 2:
        print("Usage: python mbq_parser.py <file.png>")
        raise SystemExit(1)
    pprint.pprint(get_png_metadata(sys.argv[1]))
