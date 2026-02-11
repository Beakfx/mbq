# peek_md.py
# Clean, unified dump of ComfyUI node metadata for a PNG file.

import sys
from pathlib import Path
import json
import glob

from mbq_parser import extract_json_chunks   # you already have this
from node_unify import unify_prompt_and_workflow


def trace_upstream_nodes(workflow_json):
    """
    Minimal, clean upstream traversal:
    - If workflow_json uses full schema: workflow_json['nodes'] + workflow_json['links']
    - Otherwise: return empty (no traversal possible)
    - Skips bypassed nodes
    Returns a list of nodes in proper upstream -> downstream order.
    """

    if not workflow_json or "nodes" not in workflow_json or "links" not in workflow_json:
        return []

    nodes = {n["id"]: n for n in workflow_json["nodes"]}
    links = workflow_json["links"]

    # Build reverse map: dest_id -> {src_ids}
    upstream = {}
    for link in links:
        if not isinstance(link, list) or len(link) < 5:
            continue
        _, src, _, dest, _ = link[:5]
        if isinstance(src, int) and isinstance(dest, int):
            upstream.setdefault(dest, set()).add(src)

    # Find SaveImage node(s)
    save_nodes = [n for n in nodes.values() if "saveimage" in n.get("type", "").lower()]
    if not save_nodes:
        return []

    # Use the last SaveImage (same strategy as before)
    save_id = save_nodes[-1]["id"]

    # Upstream DFS
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

        for src in upstream.get(nid, ()):
            if src not in visited:
                stack.append(src)

    # Reverse so top of chain prints first
    chain.reverse()

    # Deduplicate while preserving order
    out = []
    seen = set()
    for n in chain:
        if n["id"] not in seen:
            seen.add(n["id"])
            out.append(n)

    return out

def make_hashable(v):   # kind of a helper function
    """
    Convert lists/dicts into hashable tuples for duplicate detection.
    Keeps original structure unchanged.
    """
    if isinstance(v, list):
        return tuple(make_hashable(x) for x in v)
    if isinstance(v, dict):
        return tuple(sorted((k, make_hashable(v[k])) for k in v))
    return v

def is_useless_params(params):
    if not params:
        return True

    for k, v in params.items():
        # skip placeholder paramX keys entirely
        if k.startswith("param"):
            continue
        # empty or whitespace string
        if isinstance(v, str) and not v.strip():
            continue
        # list of booleans
        if isinstance(v, list) and all(isinstance(x, bool) for x in v):
            continue
        # empty list
        if isinstance(v, list) and not v:
            continue
        # boolean
        if isinstance(v, bool):
            continue

        # anything else is useful
        return False

    # if we never found a useful param:
    return True


def unfucked_float(v):
    if isinstance(v, float):
        # If it's close to a short decimal, round visually
        rounded = round(v, 6)
        # If rounding eliminates noise, use it
        if abs(v - rounded) < 1e-9:
            return str(rounded)
        # otherwise return raw float
        return str(v)

    return v


def clean_value(v):
    if isinstance(v, float):
        return unfucked_float(v)
    elif isinstance(v, list):
        return [clean_value(x) for x in v]
    elif isinstance(v, dict):
        return {k: clean_value(v2) for k, v2 in v.items()}
    else:
        return v

def looks_like_preview(file_stem, unified_nodes):
    """
    Decide if this PNG was likely saved from Preview/Comparer rather than a SaveImage node.
    We compare the PNG stem against any SaveImage filename_prefix values in the unified data.
    """
    prefixes = []

    for u in unified_nodes:
        if u.get("type") == "SaveImage":
            params = u.get("params", {})
            prefix = params.get("filename_prefix")
            if prefix:
                # basename of "folder/prefix"
                prefixes.append(Path(prefix).stem.lower())

    # No SaveImage in unified at all → strongly suggests preview/comparer
    if not prefixes:
        return True

    stem = file_stem.lower()

    # If filename starts with ANY SaveImage prefix → normal SaveImage output
    for p in prefixes:
        if stem.startswith(p):
            return False

    # Otherwise → saved-from-preview/comparer
    return True


def print_nicely(unified_nodes, chain):
    """
    Print unified node data:
    Node ID, Type, and named params merged from prompt & workflow.
    """
    print("Unified Node Metadata:")
    print("-" * 80)

    for node in chain:
        nid = node["id"]
        if nid not in unified_nodes:
            continue

        u = unified_nodes[nid]
        print(f"{u['id']:>4}  {u['type']}")

        params = u["params"]

        # --- Cleanup pass: remove duplicates and unwrap values ---

        cleaned = {}
        seen_values = set()

        for key, value in params.items():

            # 1. Unwrap {"__value__": ...}
            if isinstance(value, dict) and "__value__" in value:
                value = value["__value__"]

            # 2. Create hashable comparison value
            hval = make_hashable(value)

            # 3. Remove paramN if a named param has identical value
            if key.startswith("param"):
                if hval in seen_values:
                    continue
            else:
                seen_values.add(hval)

            # 4. Remove useless LoadImage "image" param duplicates
            if key.startswith("param") and value == "image":
                continue

            cleaned[key] = value

        params = cleaned

        if is_useless_params(params):
            continue

        if not params:
            continue    # just skip these
            #print("       (no params)")
        else:
            for k, v in params.items():
                # pretty-print JSON/dicts/lists for readability
                clean_v = clean_value(v)

                if isinstance(v, (dict, list)):
                    v_str = json.dumps(clean_v)
                else:
                    v_str = str(clean_v)

                # indent long values nicely
                if "\n" in v_str:
                    lines = v_str.splitlines()
                    print(f"      {k}: {lines[0]}")
                    for line in lines[1:]:
                        print(f"          {line}")
                else:
                    print(f"       {k}: {v_str}")

        print()  # blank line between nodes

    print("-" * 80)


def main():
    if len(sys.argv) < 2:
        print("Usage: peek_md.py <png_path or glob>")
        sys.exit(1)

    import glob

    # Expand globs for all arguments
    paths = []
    for arg in sys.argv[1:]:
        expanded = glob.glob(arg)
        if expanded:
            paths.extend(expanded)
        else:
            paths.append(arg)

    if not paths:
        print("No files matched.")
        sys.exit(1)

    # Process each matched file
    for filepath in paths:
        path = Path(filepath)

        print(f"-> Using workflow data from: {path.name}\n")

        prompt_json, workflow_json = extract_json_chunks(path)
        unified = unify_prompt_and_workflow(prompt_json, workflow_json)
        chain = trace_upstream_nodes(workflow_json)

            # ---- SaveImage filename match detection ----
        # unified: dict[node_id] -> node_data
        # Extract filename_prefixes from SaveImage nodes

        prefixes = []
        for u in unified.values():
            if u.get("type") == "SaveImage":
                prefix = u.get("params", {}).get("filename_prefix")
                if prefix:
                    prefixes.append(Path(prefix).stem.lower())

        png_stem = path.stem.lower()

        def filename_matches_any_prefix(png_stem, prefixes):
            for p in prefixes:
                # loose match: remove non-alphanumerics
                sp = "".join(ch for ch in p if ch.isalnum())
                ss = "".join(ch for ch in png_stem if ch.isalnum())
                if ss.startswith(sp):
                    return True
            return False

        if prefixes and not filename_matches_any_prefix(png_stem, prefixes):
            print("-> WARNING: Filename and SaveImage prefix do not match.")
            print("   Workflow metadata may not correspond to this PNG.\n")
            continue


        if not chain:
            print("No valid upstream nodes found.\n")
            continue

        print_nicely(unified, chain)
        print()  # blank line between files


if __name__ == "__main__":
    main()
