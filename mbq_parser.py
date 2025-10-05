import struct
import json
import sys
from datetime import datetime

if not sys.stdout.isatty():  # if output is redirected to file
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ============================================================
#  MAIN ENTRY
# ============================================================

def parse_png_metadata(file_path):
    """
    Extract and summarize GenAI metadata from a PNG file.
    Returns dict with detected workflow info and key parameters.
    """
    chunks = _extract_text_chunks(file_path)

    if not chunks.get("prompt_json"):
        return {"error": "No prompt JSON found", "file": file_path}

    prompt_json = chunks["prompt_json"]
    nodes = _collect_nodes(prompt_json)
    summary = _analyze_nodes(nodes)
    summary["file"] = file_path
    return summary


# ============================================================
#  CORE HELPERS
# ============================================================

def _extract_text_chunks(file_path):
    """Minimal PNG text-chunk reader to grab prompt/workflow JSON."""
    out = {}
    with open(file_path, "rb") as f:
        if f.read(8) != b"\x89PNG\r\n\x1a\n":
            return out
        while True:
            length_bytes = f.read(4)
            if not length_bytes:
                break
            length = struct.unpack(">I", length_bytes)[0]
            ctype = f.read(4).decode("ascii", "ignore")
            data = f.read(length)
            f.read(4)  # skip CRC

            if ctype == "tEXt":
                parts = data.split(b"\x00", 1)
                if len(parts) == 2:
                    key, txt = parts
                    key = key.decode("latin-1", "ignore")
                    try:
                        decoded = txt.decode("latin-1", "ignore")
                        if key == "prompt":
                            out["prompt_json"] = json.loads(decoded)
                        elif key == "workflow":
                            out["workflow_json"] = json.loads(decoded)
                    except Exception:
                        continue
            if ctype == "IEND":
                break
    return out


def _collect_nodes(prompt_json):
    """Extract node list from the prompt JSON."""
    nodes = []
    for node_id, node in prompt_json.items():
        if not isinstance(node, dict):
            continue
        node_entry = {
            "id": node_id,
            "class_type": node.get("class_type", ""),
            "title": node.get("_meta", {}).get("title", ""),
            "inputs": node.get("inputs", {}),
        }
        nodes.append(node_entry)
    return nodes


def _analyze_nodes(nodes):
    """Generate high-level workflow summary and extract key params."""
    summary = {}

    # 1️⃣ Workflow Type Hint
    summary["workflow_type"] = _guess_workflow_type(nodes)

    # 2️⃣ Extract Key Parameters
    params = _extract_key_params(nodes)
    summary.update(params)

    # 3️⃣ Node Summary
    summary["node_count"] = len(nodes)
    summary["detected_nodes"] = sorted(set(n["class_type"] for n in nodes if n["class_type"]))

    return summary


def _guess_workflow_type(nodes):
    """Simple heuristic to guess workflow type."""
    classes = [n.get("class_type", "").lower() for n in nodes]
    if any("inpaint" in c or "mask" in c for c in classes):
        return "Inpaint"
    if any("upscale" in c for c in classes):
        return "Upscale"
    if any("controlnet" in c or "adapter" in c for c in classes):
        return "ControlNet"
    if any("loadimage" in c for c in classes) and not any("empty" in c for c in classes):
        return "Image-to-Image"
    if any("empty" in c for c in classes):
        return "Text-to-Image"
    return "Unknown"


def _extract_key_params(nodes):
    """Look for common fields like model, sampler, steps, cfg, denoise, seed."""
    params = {
        "model": None,
        "sampler": None,
        "scheduler": None,
        "steps": None,
        "cfg": None,
        "denoise": None,
        "seed": None,
    }

    for node in nodes:
        inputs = node.get("inputs", {})
        for key, value in inputs.items():
            key_l = key.lower()
            if "ckpt" in key_l or "model" in key_l and isinstance(value, str):
                params["model"] = value
            elif "sampler" in key_l and isinstance(value, str):
                params["sampler"] = value
            elif "scheduler" in key_l and isinstance(value, str):
                params["scheduler"] = value
            elif "step" in key_l and _is_number(value):
                params["steps"] = value
            elif "cfg" in key_l or "guidance" in key_l:
                params["cfg"] = value
            elif "denoise" in key_l:
                params["denoise"] = value
            elif "seed" in key_l:
                params["seed"] = value

    return params


def _is_number(v):
    try:
        float(v)
        return True
    except Exception:
        return False


# ============================================================
#  CLI MODE
# ============================================================

def print_summary(result):
    """Nicely formatted console summary."""
    print("\n" + "=" * 60)
    print(f"📄 File: {result.get('file')}")
    print("=" * 60)
    if "error" in result:
        print("❌", result["error"])
        return

    print(f"Workflow Type : {result.get('workflow_type')}")
    print(f"Model         : {result.get('model')}")
    print(f"Sampler       : {result.get('sampler')}")
    print(f"Scheduler     : {result.get('scheduler')}")
    print(f"Steps         : {result.get('steps')}")
    print(f"CFG/Guidance  : {result.get('cfg')}")
    print(f"Denoise       : {result.get('denoise')}")
    print(f"Seed          : {result.get('seed')}")
    print("-" * 60)
    print(f"Detected Nodes ({result.get('node_count')}):")
    node_list = result.get("detected_nodes", [])
    for n in node_list:
        print(f"  • {n}")
    print()


if __name__ == "__main__":
    import glob
    import os

    if len(sys.argv) < 2:
        print("Usage: python mbq_parser.py <image.png> [more_images...]")
        sys.exit(1)

    input_paths = []
    for arg in sys.argv[1:]:
        expanded = glob.glob(arg)
        if expanded:
            input_paths.extend(expanded)
        elif os.path.exists(arg):
            input_paths.append(arg)
        else:
            print(f"⚠️  No match for: {arg}")

    if not input_paths:
        print("❌ No files to process.")
        sys.exit(1)

    for path in sorted(input_paths):
        result = parse_png_metadata(path)
        print_summary(result)
