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
        if not params:
            print("       (no params)")
        else:
            for k, v in params.items():
                # pretty-print JSON/dicts/lists for readability
                if isinstance(v, (dict, list)):
                    v_str = json.dumps(v)
                else:
                    v_str = str(v)

                # indent long values nicely
                if "\n" in v_str:
                    lines = v_str.splitlines()
                    print(f"       {k}: {lines[0]}")
                    for line in lines[1:]:
                        print(f"           {line}")
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

        if not chain:
            print("No valid upstream nodes found.\n")
            continue

        print_nicely(unified, chain)
        print()  # blank line between files


if __name__ == "__main__":
    main()
