from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from mbq_parser import digest_workflow, extract_json_chunks


FIELD_ORDER = [
    "workflow_type",
    "model",
    "sampler",
    "scheduler",
    "steps",
    "cfg",
    "guidance",
    "denoise",
    "seed",
    "controlnets",
    "upscale_factor",
    "style_model",
    "style_strength",
    "inpaint_mask_used",
    "prompt",
    "negative_prompt",
    "nodes",
    "saveimage_prefixes",
]

STATUS_ORDER = [
    "parsed_ok",
    "trusted_workflow",
    "trust_status",
    "ambiguity_reason",
    "error_message",
]


def resolve_inputs(target: str) -> list[Path]:
    p = Path(target)

    if any(ch in target for ch in "*?[]"):
        paths = sorted(Path().glob(target))
    elif p.is_dir():
        paths = sorted([x for x in p.iterdir() if x.is_file() and x.suffix.lower() == ".png"])
    elif p.is_file():
        paths = [p]
    else:
        raise FileNotFoundError(f"Input not found: {target}")

    pngs = [x for x in paths if x.suffix.lower() == ".png"]
    if not pngs:
        raise FileNotFoundError(f"No PNG files found for: {target}")
    return pngs



def short_text(value, max_len: int = 220) -> str:
    if value is None:
        return "None"
    if isinstance(value, str):
        s = value.replace("\r", "").replace("\n", " ").strip()
        if not s:
            return '""'
        if len(s) > max_len:
            return repr(s[:max_len] + " …")
        return repr(s)
    return repr(value)



def gui_outcome(md) -> str:
    return "SHOW_METADATA" if getattr(md, "trusted_workflow", False) else "PASS"



def basename_prefixes(prefixes: Iterable[str]) -> list[str]:
    out = []
    for prefix in prefixes or []:
        out.append(Path(str(prefix).replace("\\", "/")).name)
    return out



def write_block(o, title: str, lines: list[str]) -> None:
    o.write(title + "\n")
    o.write("-" * len(title) + "\n")
    for line in lines:
        o.write(line + "\n")
    o.write("\n")



def audit_one(path: Path, show_empty_fields: bool = False) -> str:
    prompt_json = workflow_json = None
    raw_error = None
    try:
        prompt_json, workflow_json = extract_json_chunks(path)
    except Exception as e:
        raw_error = str(e)

    md = digest_workflow(path)

    stem = path.stem
    prefixes = list(getattr(md, "saveimage_prefixes", []) or [])
    prefix_bases = basename_prefixes(prefixes)

    lines: list[str] = []
    sep = "=" * 96
    lines.append(sep)
    lines.append(f"FILE: {path.name}")
    lines.append(f"PATH: {path}")
    lines.append(f"STEM: {stem}")
    lines.append(sep)
    lines.append("")

    raw_lines = [
        f"prompt_json: {'yes' if prompt_json else 'no'}",
        f"workflow_json: {'yes' if workflow_json else 'no'}",
    ]
    if raw_error:
        raw_lines.append(f"extract_error: {raw_error}")
    write_block(lines_append_proxy(lines), "RAW PRESENCE", raw_lines)

    think_lines = [f"{name}: {short_text(getattr(md, name, None))}" for name in STATUS_ORDER]
    write_block(lines_append_proxy(lines), "CURRENT MBQ THINKING", think_lines)

    pref_lines: list[str] = []
    if prefixes:
        for raw, base in zip(prefixes, prefix_bases):
            pref_lines.append(f"raw: {short_text(raw)}")
            pref_lines.append(f"basename: {short_text(base)}")
    else:
        pref_lines.append("(none)")
    write_block(lines_append_proxy(lines), "SAVEIMAGE PREFIXES", pref_lines)

    field_lines: list[str] = []
    for name in FIELD_ORDER:
        value = getattr(md, name, None)
        if not show_empty_fields:
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            if isinstance(value, (list, tuple, dict)) and not value:
                continue
        field_lines.append(f"{name}: {short_text(value)}")
    if not field_lines:
        field_lines.append("(no populated summary fields)")
    write_block(lines_append_proxy(lines), "SUMMARY FIELDS RETURNED", field_lines)

    gui_lines = [
        f"outcome: {gui_outcome(md)}",
        f"prompt_box_source: {'prompt' if getattr(md, 'trusted_workflow', False) else short_text(getattr(md, 'ambiguity_reason', None) or 'No workflow data')}",
    ]
    write_block(lines_append_proxy(lines), "GUI CONSEQUENCE", gui_lines)

    return "\n".join(lines)


class lines_append_proxy:
    def __init__(self, store: list[str]):
        self.store = store
    def write(self, text: str) -> None:
        self.store.append(text.rstrip("\n"))



def main() -> int:
    ap = argparse.ArgumentParser(description="Audit MBQ current parser logic using the same backend as the GUI.")
    ap.add_argument("target", help="PNG file, directory, or glob pattern")
    ap.add_argument("-o", "--output", help="Write report to this text file")
    ap.add_argument("--show-empty-fields", action="store_true", help="Also show fields that are empty or None")
    args = ap.parse_args()

    paths = resolve_inputs(args.target)

    header = []
    header.append("MBQ CURRENT LOGIC AUDIT")
    header.append("=======================")
    header.append(f"Input: {args.target}")
    header.append(f"PNG count: {len(paths)}")
    header.append(f"Show empty fields: {args.show_empty_fields}")
    header.append("")

    chunks = ["\n".join(header)]
    for path in paths:
        chunks.append(audit_one(path, show_empty_fields=args.show_empty_fields))

    report = "\n".join(chunks)

    if args.output:
        out = Path(args.output)
        out.write_text(report, encoding="utf-8")
        print(f"Wrote audit to {out}")
    else:
        print(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
