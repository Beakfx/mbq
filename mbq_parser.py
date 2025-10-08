#!/usr/bin/env python3
"""
mbq_parser.py
CLI tool for analyzing genAI PNG metadata (ComfyUI, Flux, InvokeAI, etc.)
Pure-Python version — no exiftool, no external deps.
"""

import sys
import json
import struct
from pathlib import Path


# ---------------------------------------------------------------------
# 1. Extract PNG tEXt / iTXt chunks
# ---------------------------------------------------------------------
def extract_png_text_chunks(png_path: Path):
    """
    Extract all tEXt and iTXt chunks from a PNG file.
    Returns a dict of {key: value} entries.
    """
    chunks = {}
    with png_path.open("rb") as f:
        if f.read(8) != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"{png_path} is not a valid PNG")

        while True:
            length_bytes = f.read(4)
            if not length_bytes:
                break

            length = struct.unpack(">I", length_bytes)[0]
            chunk_type = f.read(4)
            data = f.read(length)
            f.read(4)  # CRC

            if chunk_type in (b"tEXt", b"iTXt"):
                try:
                    text = data.decode("utf-8", errors="ignore")
                    parts = text.split("\x00", 1)
                    if len(parts) == 2:
                        key, val = parts
                        chunks[key] = val
                except Exception:
                    continue
    return chunks


# ---------------------------------------------------------------------
# 2. Workflow classification
# ---------------------------------------------------------------------
def analyze_prompt_json(prompt_json: dict):
    """
    Given a parsed ComfyUI-style prompt JSON, return a dict of inferred metadata.
    """
    nodes = list(prompt_json.values())
    node_names = [n.get("class_type", "") for n in nodes]
    workflow_type = "Unknown"

    # --- category detection ---
    if any("Inpaint" in n for n in node_names):
        if any("Outpaint" in n for n in node_names):
            workflow_type = "Outpaint"
        else:
            workflow_type = "Inpaint"
    elif any("ControlNet" in n for n in node_names):
        workflow_type = "Img2Img+ControlNet"
    elif any("Upscale" in n for n in node_names):
        if any("Load Diffusion Model" in n or "UNETLoader" in n for n in node_names):
            workflow_type = "Upscale with Model"
        else:
            workflow_type = "Upscale"
    elif any("LoadImage" in n for n in node_names):
        workflow_type = "Img2Img"
    else:
        workflow_type = "Text-to-Image"

    # --- model detection ---
    model = None
    for node in nodes:
        inputs = node.get("inputs", {})
        if "unet_name" in inputs:
            model = inputs["unet_name"]
            break
        if "model_name" in inputs:
            model = inputs["model_name"]
            break
        if "style_model_name" in inputs:
            model = inputs["style_model_name"]
            break

    # --- sampler/scheduler/steps/cfg/denoise/seed/guidance ---
    sampler = scheduler = steps = cfg = denoise = seed = guidance = None
    for node in nodes:
        inputs = node.get("inputs", {})
        sampler = sampler or inputs.get("sampler_name")
        scheduler = scheduler or inputs.get("scheduler")
        steps = steps or inputs.get("steps")
        cfg = cfg or inputs.get("cfg")
        denoise = denoise or inputs.get("denoise")
        seed = seed or inputs.get("seed")
        guidance = guidance or inputs.get("guidance")

        # alternate forms
        if not guidance:
            if "FluxGuidance" in node.get("class_type", "") and "guidance" in inputs:
                guidance = inputs["guidance"]
            elif "BasicGuider" in node.get("class_type", "") and "guidance" in inputs:
                guidance = inputs["guidance"]

    # --- special case: only meaningful denoise in img2img or upscale ---
    if workflow_type in ("Text-to-Image", "Unknown"):
        denoise = None

    # --- node list for report ---
    detected_nodes = [n.get("class_type", "") for n in nodes]

    return {
        "workflow_type": workflow_type,
        "model": model,
        "sampler": sampler,
        "scheduler": scheduler,
        "steps": steps,
        "cfg": cfg,
        "guidance": guidance,
        "denoise": denoise,
        "seed": seed,
        "detected_nodes": detected_nodes,
    }


# ---------------------------------------------------------------------
# 3. Pretty CLI output
# ---------------------------------------------------------------------
def print_analysis(path: Path, info: dict):
    sep = "=" * 60
    print(f"\n{sep}\n📄 File: {path}\n{sep}")
    if not info:
        print("❌ No prompt JSON found")
        return

    print(f"Workflow Type : {info['workflow_type']}")
    print(f"Model         : {info['model']}")
    print(f"Sampler       : {info['sampler']}")
    print(f"Scheduler     : {info['scheduler']}")
    print(f"Steps         : {info['steps']}")
    print(f"CFG/Guidance  : {info['cfg'] or info['guidance']}")
    print(f"Denoise       : {info['denoise']}")
    print(f"Seed          : {info['seed']}")
    print("-" * 60)

    detected_nodes = info.get("detected_nodes", [])
    print(f"Detected Nodes ({len(detected_nodes)}):")
    for n in detected_nodes:
        print(f"  • {n}")


# ---------------------------------------------------------------------
# 4. Main CLI entry
# ---------------------------------------------------------------------
def analyze_file(png_path: Path):
    try:
        chunks = extract_png_text_chunks(png_path)
    except Exception as e:
        print(f"❌ Failed to read {png_path}: {e}")
        return None

    prompt_str = chunks.get("prompt") or chunks.get("Prompt")
    if not prompt_str:
        return None

    try:
        prompt_json = json.loads(prompt_str)
    except Exception as e:
        print(f"❌ JSON parse error in {png_path.name}: {e}")
        return None

    return analyze_prompt_json(prompt_json)


def main():
    if len(sys.argv) < 2:
        print("Usage: mbq_parser.py <image or folder>")
        sys.exit(1)

    target = Path(sys.argv[1])
    png_files = []
    if target.is_dir():
        png_files = list(target.glob("*.png"))
    elif target.is_file():
        png_files = [target]
    else:
        print(f"❌ Path not found: {target}")
        sys.exit(1)

    for f in png_files:
        info = analyze_file(f)
        print_analysis(f, info)


if __name__ == "__main__":
    main()

