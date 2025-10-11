# mbq_parser.py — reads and parses genAI PNG metadata fields

from __future__ import annotations
import struct, json, sys, time, glob
import zlib
from pathlib import Path
from typing import Optional, List, Dict
from mbq_metadata import ImageMetadata   # <- single shared dataclass


# -------------------------------------------------------------------
# Simple LRU cache (recent file results)
# -------------------------------------------------------------------
_CACHE: dict[str, ImageMetadata] = {}
_CACHE_MAX = 10

def _cache_put(path: str, blob: ImageMetadata):
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)))  # remove oldest
    _CACHE[path] = blob

def _cache_get(path: str) -> Optional[ImageMetadata]:
    return _CACHE.get(path)







DEBUG_PARSER = True  # set False to silence debug prints
def dbg(msg: str):
    if DEBUG_PARSER:
        print(f"[parser] {msg}")






# --- PNG chunk reader (prompt + workflow) ---------------------------


def _extract_md_chunks(file_path: str | Path):
    """
    Return {"prompt": <dict or None>, "workflow": <dict or None>}
    from PNG tEXt/iTXt/zTXt chunks.
    """
    out = {"prompt": None, "workflow": None}
    with open(file_path, "rb") as f:
        if f.read(8) != b"\x89PNG\r\n\x1a\n":
            return out

        while True:
            lb = f.read(4)
            if not lb:
                break
            length = struct.unpack(">I", lb)[0]
            ctype = f.read(4).decode("ascii", "ignore")
            data = f.read(length)
            f.read(4)  # CRC

            if ctype in ("tEXt", "iTXt", "zTXt"):
                key, _, raw = data.partition(b"\x00")
                keyword = key.decode("latin-1", "ignore").lower()

                # zTXt starts with compression flag + method (2 bytes); decompress remainder
                if ctype == "zTXt" and len(raw) >= 2:
                    try:
                        raw = zlib.decompress(raw[2:])
                    except Exception:
                        pass

                # strip stray nulls then decode
                text = raw.replace(b"\x00", b"").decode("utf-8", "ignore").strip()

                if keyword == "prompt":
                    try:
                        out["prompt"] = json.loads(text)
                    except json.JSONDecodeError:
                        out["prompt"] = None
                elif keyword == "workflow":
                    try:
                        out["workflow"] = json.loads(text)
                    except json.JSONDecodeError:
                        out["workflow"] = None

            if ctype == "IEND":
                break
    return out





# -------------------------------------------------------------------
# Core PNG metadata parser
# -------------------------------------------------------------------
def parse_png_metadata(file_path: str | Path) -> ImageMetadata:
    path = str(file_path)
    if cached := _cache_get(path):
        return cached

    # Read both prompt + workflow chunks
    chunks = _extract_md_chunks(file_path)
    prompt_json   = chunks.get("prompt")
    workflow_json = chunks.get("workflow")

    blob = ImageMetadata(file=Path(file_path), nodes=[], workflow_type="Unknown")
    # Keep raw JSON if you want to inspect later
    try:
        blob.raw_json = {"prompt": prompt_json, "workflow": workflow_json}
    except Exception:
        pass

    if not prompt_json:
        _cache_put(path, blob)
        return blob

    # For UI “nodes” list, store titles or class names (read-only nicety)
    blob.nodes = [
        (n.get("_meta", {}) or {}).get("title") or n.get("class_type", "?")
        for n in prompt_json.values()
    ]

    # --- Detection pipeline (unchanged pieces) ---
    blob.workflow_type = _detect_workflow_type(prompt_json)
    blob.model        = _detect_model(prompt_json)
    blob.sampler      = _detect_sampler(prompt_json)
    blob.scheduler    = _detect_scheduler(prompt_json)
    blob.steps        = _detect_steps(prompt_json)
    blob.cfg          = _detect_cfg(prompt_json)
    blob.denoise      = _detect_denoise(prompt_json)
    blob.seed         = _detect_seed(prompt_json)
    blob.controlnets  = _detect_controlnets(prompt_json)

    # --- NEW: robust prompt resolution (graph-first, fallback semantic) ---
    pos, neg = _detect_prompts_via_graph(file_path, prompt_json, workflow_json)
    if not pos:
        # Fallback: first text encoder found (keeps old behavior for legacy images)
        pos = _detect_prompt(prompt_json)
    blob.prompt = pos
    blob.negative_prompt = neg

    _cache_put(path, blob)
    return blob


# -------------------------------------------------------------------
# Chunk extractor
# -------------------------------------------------------------------
def _extract_prompt_json(file_path: str | Path):
    """Extract embedded JSON from PNG tEXt chunks."""
    with open(file_path, "rb") as f:
        if f.read(8) != b"\x89PNG\r\n\x1a\n":
            return None

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
                if key.decode("latin-1") == "prompt":
                    try:
                        return json.loads(txt.decode("latin-1"))
                    except json.JSONDecodeError:
                        return None

            if ctype == "IEND":
                break
    return None


# -------------------------------------------------------------------
# Detection helpers
# -------------------------------------------------------------------
def _detect_workflow_type(nodes):
    classes = [n.get("class_type", "").lower() for n in nodes.values()]
    has_loadimg   = any("loadimage" in c for c in classes)
    has_inpaint   = any("inpaint" in c for c in classes)
    has_upscale   = any("upscale" in c for c in classes)
    has_control   = any("controlnet" in c for c in classes)

    if not has_loadimg:
        return "Text-to-Image"
    if has_inpaint:
        return "Outpaint" if any("extend" in c for c in classes) else "Inpaint"
    if has_upscale:
        return "Upscale"
    if has_control:
        return "ControlNet"
    return "Image-to-Image"


def _find_first(nodes, key):
    for n in nodes.values():
        if key in n.get("inputs", {}):
            return n["inputs"].get(key)
    return None


def _detect_model(nodes):
    """Detect primary model or checkpoint reference."""
    loader_classes = {
        "CheckpointLoaderSimple", "CheckpointLoader",
        "UNETLoader", "FluxUNETLoader", "FluxModelLoader",
        "ControlNetLoader", "UpscaleModelLoader",
        "IPAdapterLoader", "LoraLoader"
    }

    for n in nodes.values():
        ctype = n.get("class_type", "")
        if ctype in loader_classes:
            inputs = n.get("inputs", {})
            for k in (
                "ckpt_name", "unet_name", "model_name",
                "lora_name", "control_net_name",
                "ckpt_file", "base_model"
            ):
                if k in inputs:
                    name = inputs[k]
                    if isinstance(name, str):
                        return Path(name).stem
                    return name
    return None


def _detect_sampler(nodes):   return _find_first(nodes, "sampler_name")
def _detect_scheduler(nodes): return _find_first(nodes, "scheduler")
def _detect_steps(nodes):     return _find_first(nodes, "steps")
def _detect_cfg(nodes):       return _find_first(nodes, "cfg") or _find_first(nodes, "guidance")
def _detect_denoise(nodes):   return _find_first(nodes, "denoise")
def _detect_seed(nodes):      return _find_first(nodes, "seed") or _find_first(nodes, "noise_seed")


def _detect_controlnets(nodes):
    found = []
    for n in nodes.values():
        ctype = n.get("class_type", "")
        if "controlnet" in ctype.lower():
            found.append(ctype)
        for v in n.get("inputs", {}).values():
            if isinstance(v, str) and "controlnet" in v.lower():
                found.append(v)
    return sorted(set(found))


def _detect_prompt(nodes):
    """Find first text input (complete string)."""
    for n in nodes.values():
        t = n.get("inputs", {}).get("text")
        if isinstance(t, str) and t.strip():
            return t.strip()
    return None



# --- Graph-based prompt resolution ---------------------------------
def _build_graph(workflow):
    nodes = {str(n["id"]): n for n in (workflow or {}).get("nodes", [])}
    in_edges = {nid: [] for nid in nodes}
    out_edges = {nid: [] for nid in nodes}
    for link in (workflow or {}).get("links", []):
        # link format: [id, from_id, from_slot, to_id, to_slot, "TYPE"]
        _, from_id, from_slot, to_id, to_slot, _ = link
        from_id, to_id = str(from_id), str(to_id)
        out_edges[from_id].append((to_id, from_slot, to_slot))
        in_edges[to_id].append((from_id, from_slot, to_slot))
    return nodes, in_edges, out_edges

def _select_saveimage_for_file(file_path: str | Path, nodes):
    """Pick the SaveImage most likely responsible for this filename."""
    stem = Path(file_path).stem.lower()
    token = stem.split("_")[0] if "_" in stem else stem

    cands = []
    for n in nodes.values():
        ctype = (n.get("type") or n.get("class_type") or "").lower()
        if ctype != "saveimage":
            continue
        cands.append(n)
        # Prefer prefix match if present
        wv = n.get("widgets_values") or []
        prefix = (str(wv[0]).lower() if isinstance(wv, list) and wv else "")
        if prefix and token and token in prefix:
            return n

    # Fallback: any SaveImage with an input link named "images"
    for n in cands:
        if any(inp.get("name") == "images" and inp.get("link") is not None for inp in n.get("inputs", [])):
            return n

    return cands[0] if cands else None
def _is_text_encoder(nid: str, prompt_nodes) -> bool:
    p = prompt_nodes.get(str(nid))
    if not p:
        return False
    c = p.get("class_type", "").lower()
    return "cliptextencode" in c  # covers CLIPTextEncode & CLIPTextEncodeFlux

def _extract_text_from_prompt_node(nid: str, prompt_nodes) -> str | None:
    """Return full text from CLIP encoders, merging Flux subfields."""
    p = prompt_nodes.get(str(nid))
    if not p:
        return None
    c = p.get("class_type", "").lower()
    inputs = p.get("inputs", {}) or {}
    if "cliptextencodeflux" in c:
        parts = []
        for k in ("clip_l", "clip_g", "t5xxl", "text"):
            v = inputs.get(k)
            if isinstance(v, str) and v.strip():
                parts.append(v.strip())
        return "\n".join(parts) if parts else None
    # plain CLIPTextEncode
    t = inputs.get("text")
    return t.strip() if isinstance(t, str) and t.strip() else None

def _find_upstream_of_type(start_id: str, nodes, in_edges, wanted_types: set[str]):
    """Walk upstream BFS to find first node whose class/type is in wanted_types."""
    seen, q = set(), [start_id]
    while q:
        nid = q.pop(0)
        if nid in seen:
            continue
        seen.add(nid)
        n = nodes.get(nid) or {}
        ctype = (n.get("type") or n.get("class_type") or "").lower()
        if ctype in wanted_types:
            return n
        for (src, _, _) in in_edges.get(nid, []):
            q.append(src)
    return None



def _collect_conditioning_text(start_link_id: int | None, nodes, in_edges, prompt_nodes) -> str | None:
    """
    We get link IDs in workflow inputs, but the workflow JSON in Comfy stores node IDs on links array,
    while prompt JSON gives us encoder classes and actual text. We walk upstream by node id and
    stop at the first CLIP encoder(s), then merge their texts.
    """
    if start_link_id is None:
        return None
    # We don't have link->node map here, but in_edges on the target node carries (src_id, ...)
    # Callers pass node ids (not raw link ids) when available; handle both defensively.
    texts, seen, stack = [], set(), [str(start_link_id)]
    while stack:
        nid = stack.pop()
        if nid in seen:
            continue
        seen.add(nid)

        # If this node is a text encoder in prompt JSON, extract text
        if _is_text_encoder(nid, prompt_nodes):
            txt = _extract_text_from_prompt_node(nid, prompt_nodes)
            if txt:
                texts.append(txt)
            # Don't traverse past encoders
            continue

        # Otherwise, keep walking upstream
        for (src, _, _) in in_edges.get(nid, []):
            stack.append(src)

    return "\n".join(t for t in texts if t) or None

def _detect_prompts_via_graph(file_path: str | Path, prompt_json: dict | None, workflow_json: dict | None):
    """Return (positive_text, negative_text) using actual path to SaveImage."""


    if not workflow_json or not prompt_json:
        return None, None

    nodes, in_edges, _ = _build_graph(workflow_json)
    
    ###debugger prints  down here
    dbg(f"🔍 Starting prompt detection for workflow with {len(nodes)} nodes")

    save = _select_saveimage_for_file(file_path, nodes)
    dbg(f"save node -> {save.get('id') if save else 'None'}")
    if not save:
        return None, None

    # Find VAEDecode upstream of SaveImage (robust across stitchers etc.)
    vae = _find_upstream_of_type(str(save["id"]), nodes, in_edges, {"vaedecode"})
    dbg(f"vae node -> {vae.get('id') if vae else 'None'}")
    if not vae:
        return None, None

    # Find sampler upstream of VAEDecode
    sampler = _find_upstream_of_type(str(vae["id"]), nodes, in_edges, {"ksampler", "modelsamplingsd3", "modelsampling"})
    dbg(f"sampler node -> {sampler.get('id') if sampler else 'None'}")
    if not sampler:
        return None, None

    # Get node ids that feed 'positive'/'negative' inputs (via workflow inputs with 'link' ids)
    pos_link = next((inp.get("link") for inp in sampler.get("inputs", []) if inp.get("name") == "positive"), None)
    neg_link = next((inp.get("link") for inp in sampler.get("inputs", []) if inp.get("name") == "negative"), None)







    # In Comfy workflow JSON, input.link holds the id of the link, not the src node id.
    # But in_edges on the sampler node carries (src_id, from_slot, to_slot) for *all* links.
    # Filter in_edges by the destination slot name to find the src node id.
    def _find_src_for_slot(sampler_node, slot_name: str):
        # get the numeric slot index for that slot name
        slot_idx = None
        for i, inp in enumerate(sampler_node.get("inputs", [])):
            if inp.get("name") == slot_name:
                slot_idx = inp.get("slot_index") if "slot_index" in inp else i
                break
        if slot_idx is None:
            return None
        for (src, _from, to_slot) in in_edges.get(str(sampler_node["id"]), []):
            if to_slot == slot_idx:
                return src
        return None

    pos_src = _find_src_for_slot(sampler, "positive")
    neg_src = _find_src_for_slot(sampler, "negative")

    # Walk back to find encoders and extract text (Flux merge supported)
    positive = _collect_conditioning_text(pos_src, nodes, in_edges, prompt_json) if pos_src else None
    negative = _collect_conditioning_text(neg_src, nodes, in_edges, prompt_json) if neg_src else None

    return positive, negative



# -------------------------------------------------------------------
# CLI entrypoint
# -------------------------------------------------------------------
def _print_summary(blob: ImageMetadata):
    print("=" * 60)
    print(f"📄 File          : {blob.file}")
    print("=" * 60)
    print(f"Workflow Type   : {blob.workflow_type}")
    print(f"Model           : {blob.model}")
    print(f"Sampler         : {blob.sampler}")
    print(f"Scheduler       : {blob.scheduler}")
    print(f"Steps           : {blob.steps}")
    print(f"CFG/Guidance    : {blob.cfg}")
    print(f"Denoise         : {blob.denoise}")
    print(f"Seed            : {blob.seed}")
    if blob.controlnets:
        print(f"ControlNets     : {blob.controlnets}")
    if blob.prompt:
        print(f"Prompt (trunc)  : {blob.prompt}")
    print("-" * 60)
    print("Detected Nodes:")
    for title in (blob.nodes or []):
        print(f"  • {title}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python mbq_parser.py <file.png or folder>")
        sys.exit(1)

    target = Path(sys.argv[1])
    files = list(target.glob("*.png")) if target.is_dir() else glob.glob(str(target))

    for f in files:
        blob = parse_png_metadata(f)
        _print_summary(blob)

