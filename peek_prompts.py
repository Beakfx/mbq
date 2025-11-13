
# peek_prompts.py — traverse ComfyUI workflow or prompt

import sys
import os
import json
from pathlib import Path
from mbq_parser import extract_json_chunks

def find_matching_save_node(workflow, file_path):
    """Return the SaveImage node whose filename prefix matches the image file."""
    if not workflow or "nodes" not in workflow:
        return None

    base = Path(file_path).stem.lower()  # e.g. "disc_fix_00006_"
    nodes = workflow.get("nodes", [])
    for node in nodes:
        if "saveimage" not in node.get("type", "").lower():
            continue
        vals = node.get("widgets_values", [])
        if not vals:
            continue
        prefix = str(vals[0]).lower()
        # remove directories and compare stems
        prefix_name = os.path.basename(prefix)
        if prefix_name in base or base.startswith(prefix_name):
            return node
    return None

def trace_upstream_nodes(workflow, start_node=None):
    """Return non-bypassed nodes feeding into the chosen SaveImage (or last one), workflow & prompt aware."""

    if not workflow:
        return []

    # --- Build nodes and links based on schema ---
    if "nodes" in workflow and "links" in workflow:
        # Workflow schema
        nodes = {n["id"]: n for n in workflow["nodes"]}
        links = workflow["links"]
    else:
        # Prompt schema: synthesize nodes/links
        nodes = {}
        links = []
        for k, v in workflow.items():
            if not isinstance(v, dict):
                continue
            try:
                nid = int(k)
            except Exception:
                continue
            node = dict(v)
            node["id"] = nid
            node["type"] = node.get("type", node.get("class_type", ""))
            nodes[nid] = node
            inputs = node.get("inputs", {})
            if isinstance(inputs, dict):
                for val in inputs.values():
                    if isinstance(val, list) and len(val) >= 2:
                        try:
                            src_id = int(val[0])
                        except Exception:
                            continue
                        links.append(["auto", src_id, 0, nid, 0])

    # --- Choose the start SaveImage node ---
    if start_node is not None:
        # trust the caller's chosen SaveImage
        save_id = start_node["id"]
    else:
        save_nodes = [n for n in nodes.values() if "saveimage" in n.get("type", "").lower()]
        if not save_nodes:
            return []
        save_id = save_nodes[-1]["id"]

    # --- Build dest->sources map from links ---
    upstream_map = {}
    for link in links:
        if not isinstance(link, list) or len(link) < 5:
            continue
        try:
            _, src_id, _, dest_id, _ = link[:5]
        except Exception:
            continue
        if isinstance(src_id, int) and isinstance(dest_id, int):
            upstream_map.setdefault(dest_id, set()).add(src_id)

    # --- Traverse upstream from the chosen SaveImage ---
    chain = []
    visited = set()
    stack = [save_id]

    while stack:
        nid = stack.pop()
        if nid in visited:
            continue
        visited.add(nid)
        node = nodes.get(nid)
        if node and not node.get("bypass", False):
            chain.append(node)
        for src in upstream_map.get(nid, ()):
            if src not in visited:
                stack.append(src)

    # upstream first
    chain = list(reversed(chain))

    # optional: unique by id while preserving order
    seen = set()
    chain = [n for n in chain if not (n["id"] in seen or seen.add(n["id"]))]

    return chain


def print_workflow_summary(file_path: str):
    """Print a table of all non-bypassed upstream nodes feeding the active SaveImage node."""
    prompt_json, workflow_json = extract_json_chunks(Path(file_path))

    # Prefer prompt data (runtime execution graph), fallback to workflow (UI graph)
    data_json = workflow_json

    print(f"-> Using {'workflow' if workflow_json else 'prompt'} data for {os.path.basename(file_path)}")

    
    if not data_json:
            print(f"\n{os.path.basename(file_path)}")
            print("  (no prompt or workflow JSON found)")
            print("-" * 80)
            return

    save_node = find_matching_save_node(data_json, file_path)
    chain = trace_upstream_nodes(data_json, start_node=save_node)

    if not chain:
        print(f"\n{os.path.basename(file_path)}")
        print("  (no SaveImage or upstream nodes found)")
        print("-" * 80)
        return

    print(f"\n{os.path.basename(file_path)}")
    print(f"{'Node ID':<8} {'Node Type':<32} {'Widget/Input Values':<80}")
    print("-" * 120)

    for node in chain:
        wval = ""
        source_tag = ""
        has_values = False  # flag to mark nodes that truly have content

        # --- Case 1: Classic widgets_values array ---
        if node.get("widgets_values") is not None:
            vals = node.get("widgets_values", [])
            source_tag = "[W]"
            if not vals:
                source_tag += "[X]"  # explicitly empty list
            else:
                has_values = True
                formatted = []
                for v in vals:
                    if isinstance(v, (list, dict)):
                        formatted.append(json.dumps(v))
                    else:
                        formatted.append(str(v))
                wval = ", ".join(formatted)

        # --- Case 2: Dict-style inputs map or list ---
        elif node.get("inputs"):
            inputs = node["inputs"]
            source_tag = "[I]"
            kv_pairs = []

            if isinstance(inputs, dict):
                for k, v in inputs.items():
                    if isinstance(v, list) and v and isinstance(v[0], (str, int)):
                        kv_pairs.append(f"{k}={v[0]}")
                    elif isinstance(v, (str, int, float)):
                        kv_pairs.append(f"{k}={v}")
            elif isinstance(inputs, list):
                for entry in inputs:
                    if isinstance(entry, dict):
                        name = entry.get("name", "?")
                        link = entry.get("link")
                        if link is not None:
                            kv_pairs.append(f"{name}={link}")
                        else:
                            kv_pairs.append(name)
                    else:
                        kv_pairs.append(str(entry))

            if kv_pairs:
                wval = ", ".join(kv_pairs)
                has_values = True

        # --- Case 3: no widgets or inputs at all ---
        else:
            source_tag = "[X]"  # completely empty node

        # Truncate long values for readability
        if len(wval) > 78:
            wval = wval[:75] + "..."

        node_type = node.get("type", node.get("class_type", ""))
        print(f"{node.get('id','?'):<8} {node_type:<32} {source_tag} {wval}")



    # --- Categorize nodes by role ---
    groups = {
        "Text Encoders": [],
        "Samplers": [],
        "Models Loaded": [],
    }

    # --- Gather from workflow nodes ---
    for node in chain:
        ntype = node.get("type", node.get("class_type", ""))
        vals = node.get("widgets_values", [])
        text_vals = [str(v) for v in vals if isinstance(v, str) and v.strip()]
        joined = ", ".join(text_vals) if text_vals else ""
        ntype_lower = ntype.lower()

        # Group 1: Text Encoders
        if "textencode" in ntype_lower:
            if joined:
                groups["Text Encoders"].append(joined)

        # Group 2: Samplers
        elif "sampler" in ntype_lower:
            if joined:
                groups["Samplers"].append(joined)

        # Group 3: Model Loaders
        elif any(x in ntype_lower for x in ["loader", "model", "checkpoint"]):
            if joined:
                groups["Models Loaded"].append(joined)


    # --- Pretty print grouped summary ---
    print("\nGrouped Summary:")
    print("-" * 120)
    for label, items in groups.items():
        if items:
            print(f"{label}:")
            for item in items:
                print(f"  • {item}")
            print()
    print("-" * 120)




def main():
    if len(sys.argv) < 2:
        print("Usage: peek_prompts.py <glob_or_path>")
        sys.exit(1)

    paths = []
    for arg in sys.argv[1:]:
        paths.extend(Path().glob(arg))

    print(f"Scanning {len(paths)} file(s)...\n")
    for p in paths:
        print_workflow_summary(str(p))


if __name__ == "__main__":
    main()
