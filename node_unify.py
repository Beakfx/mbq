# node_unify.py
# Unified prompt/workflow merge with correct Comfy alignment rules.

import unicodedata


def normalize_value(v):
    if v is None or v == "None":
        return None

    if isinstance(v, bool):
        return v

    if isinstance(v, (int, float)):
        return float(v)

    if isinstance(v, list):
        return [normalize_value(x) for x in v]

    if isinstance(v, dict):
        return {k: normalize_value(val) for k, val in v.items()}

    if isinstance(v, str):
        s = v.strip()
        s = unicodedata.normalize("NFKC", s)
        s = s.replace("\r\n", "\n").replace("\r", "\n")

        try:
            return float(s)
        except:
            return s

    s = str(v).strip()
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    return s


def values_equivalent(a, b):
    return normalize_value(a) == normalize_value(b)


def unify_prompt_and_workflow(prompt_json, workflow_json):
    prompt_nodes = {}
    if prompt_json:
        for k, v in prompt_json.items():
            if isinstance(v, dict):
                try:
                    prompt_nodes[int(k)] = v
                except:
                    pass

    workflow_nodes = {}
    if workflow_json and "nodes" in workflow_json:
        for n in workflow_json["nodes"]:
            nid = n.get("id")
            if isinstance(nid, int):
                workflow_nodes[nid] = n

    all_ids = set(prompt_nodes.keys()) | set(workflow_nodes.keys())
    unified = {}

    for nid in sorted(all_ids):
        pnode = prompt_nodes.get(nid)
        wnode = workflow_nodes.get(nid)

        if pnode and "class_type" in pnode:
            ntype = pnode["class_type"]
        elif pnode and "type" in pnode:
            ntype = pnode["type"]
        elif wnode and "type" in wnode:
            ntype = wnode["type"]
        else:
            ntype = "Unknown"

        params = {}

        # PROMPT LITERAL INPUTS (skip links)
        prompt_literal_values = []
        prompt_literal_keys = []

        if pnode and "inputs" in pnode:
            for key, val in pnode["inputs"].items():
                # Link input → skip (not a literal)
                if isinstance(val, list) and len(val) == 2 and isinstance(val[0], str):
                    continue

                params[key] = val
                prompt_literal_keys.append(key)
                prompt_literal_values.append(val)

        # WORKFLOW WIDGETS
        w_values = wnode.get("widgets_values", []) if wnode else []

        # --- Smart synchronization between prompt literal inputs and workflow widget values ---
        skip_indices = set()
        i = 0  # index for prompt literal values
        j = 0  # index for workflow values

        while i < len(prompt_literal_values) and j < len(w_values):

            if values_equivalent(prompt_literal_values[i], w_values[j]):
                # They match → skip this workflow param (no param#)
                skip_indices.add(j)
                i += 1
                j += 1
            else:
                # They do NOT match → workflow has an extra value here
                # Mark this as param#, but DO NOT advance prompt index
                j += 1

        # After loop, all remaining workflow values are extras → include as paramN
        for idx, val in enumerate(w_values):
            if idx not in skip_indices:
                params[f"param{idx}"] = val


        unified[nid] = {
            "id": nid,
            "type": ntype,
            "params": params
        }

    return unified
