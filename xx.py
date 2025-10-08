import struct, json, sys, os, glob

def parse_png_metadata(file_path):
    data = _extract_text_chunks(file_path)
    prompt_json = data.get("prompt_json")
    if not prompt_json:
        return {"error": "No prompt JSON found"}

    return _analyze_prompt(prompt_json)


def _extract_text_chunks(file_path):
    """Minimal PNG text-chunk extractor"""
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
            f.read(4)
            if ctype == "tEXt":
                parts = data.split(b"\x00", 1)
                if len(parts) == 2:
                    key, txt = parts
                    if key.decode("latin-1") == "prompt":
                        out["prompt_json"] = json.loads(txt.decode("latin-1"))
            if ctype == "IEND":
                break
    return out


def _analyze_prompt(prompt_json):
    """Working analyzer stub"""
    nodes = list(prompt_json.values())
    node_types = [n.get("class_type") for n in nodes if isinstance(n, dict)]

    # Simple heuristic workflow detection
    if any("Inpaint" in n for n in node_types):
        wtype = "Inpaint"
    elif any("Upscale" in n for n in node_types):
        wtype = "Upscale"
    elif any("ControlNet" in n for n in node_types):
        wtype = "ControlNet"
    else:
        wtype = "Text-to-Image"

    params = {}
    for n in nodes:
        if not isinstance(n, dict):
            continue
        inputs = n.get("inputs", {})
        for key in ["seed", "steps", "cfg", "guidance", "sampler_name", "scheduler", "denoise"]:
            if key in inputs:
                params[key] = inputs[key]
        if "unet_name" in inputs:
            params["model"] = inputs["unet_name"]
        if "model_name" in inputs:
            params["upscale_model"] = inputs["model_name"]

    return {
        "Workflow Type": wtype,
        "Model": params.get("model"),
        "Sampler": params.get("sampler_name"),
        "Scheduler": params.get("scheduler"),
        "Steps": params.get("steps"),
        "CFG/Guidance": params.get("cfg") or params.get("guidance"),
        "Denoise": params.get("denoise"),
        "Seed": params.get("seed"),
        "ControlNets": _detect_controlnets(prompt_json),
        "Detected Nodes": sorted(set(node_types)),
    }


def _detect_controlnets(prompt_json):
    """Find ControlNet nodes and infer type if possible."""
    detected = set()

    for node in prompt_json.values():
        if not isinstance(node, dict):
            continue

        ctype = node.get("class_type", "")
        if "ControlNet" not in ctype:
            continue

        # Skip boilerplate plumbing nodes
        if any(skip in ctype for skip in ["ControlNetApply", "ControlNetPreprocess", "ControlNetCombine"]):
            continue

        # Try to infer subtype from filenames or model names
        subtype = None
        for v in node.get("inputs", {}).values():
            if isinstance(v, str):
                for tag in ["canny", "depth", "normal", "segment", "openpose", "lineart", "mlsd", "union", "tile"]:
                    if tag in v.lower():
                        subtype = tag
                        break
            if subtype:
                break

        # Default to the core type name if no subtype found
        if subtype:
            detected.add(subtype.capitalize())
        else:
            # catch generic e.g. "ControlNetLoader"
            detected.add("Generic")

    # Cleanly sorted, no duplicates
    return sorted(detected)




def print_report(results):
    for file, res in results.items():
        print("=" * 60)
        print(f"📄 File: {file}")
        print("=" * 60)
        if "error" in res:
            print("❌", res["error"])
        else:
            for k, v in res.items():
                if k == "Detected Nodes":
                    print("-" * 60)
                    print("Detected Nodes:")
                    for node in v:
                        print("  •", node)
                else:
                    print(f"{k:15}: {v}")
        print("\n")


if __name__ == "__main__":
    paths = []
    for arg in sys.argv[1:]:
        paths.extend(glob.glob(arg))
    if not paths:
        print("Usage: python mbq_parser.py images\\*.png")
        sys.exit(1)

    results = {}
    for path in paths:
        results[path] = parse_png_metadata(path)

    print_report(results)
