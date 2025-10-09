#mbq_parser -> reads and parses, with some added logic, genAI png metadata fileds

from __future__ import annotations
import struct, json, sys, time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from typing import List, Optional, Dict


# -------------------------------------------------------------------
# Data structure for parsed metadata
# -------------------------------------------------------------------
@dataclass
class ImageMetadata:
    file: Path
    workflow_type: str = "Unknown"
    model: Optional[str] = None
    sampler: Optional[str] = None
    scheduler: Optional[str] = None
    steps: Optional[int] = None
    cfg: Optional[float] = None
    denoise: Optional[float] = None
    seed: Optional[int] = None
    controlnets: list[str] = None
    prompt: Optional[str] = None
    raw_nodes: list[dict] = None
    timestamp: float = time.time()

    def as_dict(self):
        """Convenient dict export for UI."""
        return asdict(self)

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

# -------------------------------------------------------------------
# Core PNG metadata parser
# -------------------------------------------------------------------
def parse_png_metadata(file_path: str | Path) -> ImageMetadata:
    path = str(file_path)
    if cached := _cache_get(path):
        return cached

    prompt_json = _extract_prompt_json(file_path)
    blob = ImageMetadata(file=Path(file_path), raw_nodes=[])

    if not prompt_json:
        _cache_put(path, blob)
        return blob

    blob.raw_nodes = list(prompt_json.values())

    # Workflow classification
    blob.workflow_type = _detect_workflow_type(prompt_json)
    blob.model = _detect_model(prompt_json)
    blob.sampler = _detect_sampler(prompt_json)
    blob.scheduler = _detect_scheduler(prompt_json)
    blob.steps = _detect_steps(prompt_json)
    blob.cfg = _detect_cfg(prompt_json)
    blob.denoise = _detect_denoise(prompt_json)
    blob.seed = _detect_seed(prompt_json)
    blob.controlnets = _detect_controlnets(prompt_json)
    blob.prompt = _detect_prompt(prompt_json)

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
    has_loadimg = any("loadimage" in c for c in classes)
    has_inpaint = any("inpaint" in c for c in classes)
    has_upscale = any("upscale" in c for c in classes)
    has_controlnet = any("controlnet" in c for c in classes)
    if not has_loadimg:
        return "Text-to-Image"
    if has_inpaint:
        if any("extend" in c for c in classes):
            return "Outpaint"
        return "Inpaint"
    if has_upscale:
        return "Upscale"
    if has_controlnet:
        return "ControlNet"
    return "Image-to-Image"

def _find_first(nodes, key):
    for n in nodes.values():
        if key in n.get("inputs", {}):
            return n["inputs"].get(key)
    return None

def _detect_model(nodes):
    for n in nodes.values():
        inputs = n.get("inputs", {})
        for k in ("unet_name", "model_name", "checkpoint", "style_model_name"):
            if k in inputs:
                return inputs[k]
    return None

def _detect_sampler(nodes):
    return _find_first(nodes, "sampler_name")

def _detect_scheduler(nodes):
    return _find_first(nodes, "scheduler")

def _detect_steps(nodes):
    return _find_first(nodes, "steps")

def _detect_cfg(nodes):
    return _find_first(nodes, "cfg") or _find_first(nodes, "guidance")

def _detect_denoise(nodes):
    return _find_first(nodes, "denoise")

def _detect_seed(nodes):
    return _find_first(nodes, "seed") or _find_first(nodes, "noise_seed")

def _detect_controlnets(nodes):
    found = []
    for n in nodes.values():
        ctype = n.get("class_type", "")
        if "controlnet" in ctype.lower():
            found.append(ctype)
        for k, v in n.get("inputs", {}).items():
            if isinstance(v, str) and "controlnet" in v.lower():
                found.append(v)
    return sorted(set(found))

def _detect_prompt(nodes):
    """Find first text input (shortened)."""
    for n in nodes.values():
        t = n.get("inputs", {}).get("text")
        if isinstance(t, str) and len(t) > 0:
            return t[:240] + ("..." if len(t) > 240 else "")
    return None

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
    for n in blob.raw_nodes:
        title = n.get("_meta", {}).get("title") or n.get("class_type")
        print(f"  • {title}")
    print()

if __name__ == "__main__":
    import glob
    if len(sys.argv) < 2:
        print("Usage: python mbq_parser.py <file.png or folder>")
        sys.exit(1)

    target = Path(sys.argv[1])
    files = []
    if target.is_dir():
        files = list(target.glob("*.png"))
    else:
        files = glob.glob(str(target))

    for f in files:
        blob = parse_png_metadata(f)
        _print_summary(blob)

@dataclass
class ImageMetadata:
    """Unified structure for parsed genAI metadata (MB data)"""

    # Core identifiers
    filename: str
    workflow_type: Optional[str] = None
    model: Optional[str] = None

    # Generation parameters
    sampler: Optional[str] = None
    scheduler: Optional[str] = None
    steps: Optional[int] = None
    guidance: Optional[float] = None
    denoise: Optional[float] = None
    seed: Optional[int] = None

    # ControlNet / upscale / style / inpaint info
    controlnets: List[str] = field(default_factory=list)
    upscale_factor: Optional[float] = None
    style_model: Optional[str] = None
    style_strength: Optional[float] = None
    inpaint_mask_used: Optional[bool] = None

    # Prompt & text data
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None

    # Detected node list
    nodes: List[str] = field(default_factory=list)

    # Internal / system fields
    raw_json: Optional[Dict] = None
    parsed_ok: bool = True
    error_message: Optional[str] = None

    # Pretty-print helper
    def summary(self) -> str:
        """Simple readable summary for CLI or log output"""
        parts = [
            f"Workflow: {self.workflow_type or 'Unknown'}",
            f"Model: {self.model or '—'}",
            f"Steps: {self.steps or '—'}",
            f"CFG: {self.guidance or '—'}",
            f"Denoise: {self.denoise or '—'}",
            f"Seed: {self.seed or '—'}",
        ]
        if self.controlnets:
            parts.append(f"ControlNets: {', '.join(self.controlnets)}")
        return " | ".join(parts)
