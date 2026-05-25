from __future__ import annotations
import argparse
import json
import re
import struct
from pathlib import Path
from typing import Any

from mbq_parser import extract_json_chunks
from mbq_nodes import parse_nodes


def normalize_name(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', s.lower())


def png_size(path: Path):
    try:
        with open(path, 'rb') as f:
            if f.read(8) != b"\x89PNG\r\n\x1a\n":
                return None, None
            length = struct.unpack('>I', f.read(4))[0]
            ctype = f.read(4)
            if ctype != b'IHDR' or length < 8:
                return None, None
            width = struct.unpack('>I', f.read(4))[0]
            height = struct.unpack('>I', f.read(4))[0]
            return width, height
    except Exception:
        return None, None


def prompt_saveimage_prefixes(prompt_json: Any):
    out = []
    if not isinstance(prompt_json, dict):
        return out
    for nid, node in prompt_json.items():
        if not isinstance(node, dict):
            continue
        if node.get('class_type') != 'SaveImage':
            continue
        inputs = node.get('inputs', {})
        prefix = inputs.get('filename_prefix')
        out.append({
            'id': nid,
            'source': 'prompt',
            'class_type': node.get('class_type'),
            'filename_prefix': prefix,
        })
    return out


def workflow_saveimage_prefixes(workflow_json: Any):
    out = []
    if not isinstance(workflow_json, dict):
        return out
    for node in workflow_json.get('nodes', []):
        if not isinstance(node, dict):
            continue
        if node.get('type') != 'SaveImage':
            continue
        wv = node.get('widgets_values', [])
        prefix = wv[0] if wv else None
        out.append({
            'id': node.get('id'),
            'source': 'workflow',
            'type': node.get('type'),
            'filename_prefix': prefix,
        })
    return out


def write_section(fh, title: str):
    fh.write(f"\n{title}\n")
    fh.write(f"{'=' * len(title)}\n")


def write_json_block(fh, title: str, obj: Any):
    write_section(fh, title)
    if obj is None:
        fh.write('(none)\n')
    else:
        fh.write(json.dumps(obj, indent=2, ensure_ascii=False))
        fh.write('\n')


def dump_one_png(path: Path, fh, full_json: bool = False):
    fh.write('\n' + '#' * 100 + '\n')
    fh.write(f"FILE: {path.name}\n")
    fh.write(f"PATH: {path}\n")
    width, height = png_size(path)
    fh.write(f"SIZE: {width} x {height}\n" if width and height else 'SIZE: (unknown)\n')
    fh.write('#' * 100 + '\n')

    prompt_json, workflow_json = extract_json_chunks(path)

    fh.write(f"prompt_json: {'yes' if prompt_json else 'no'}\n")
    fh.write(f"workflow_json: {'yes' if workflow_json else 'no'}\n")

    if not prompt_json and not workflow_json:
        fh.write('RESULT: no prompt/workflow JSON found\n')
        return

    save_nodes = prompt_saveimage_prefixes(prompt_json) + workflow_saveimage_prefixes(workflow_json)

    write_section(fh, 'SaveImage prefix candidates')
    if not save_nodes:
        fh.write('(none found)\n')
    else:
        stem_norm = normalize_name(path.stem)
        fh.write(f"normalized filename stem: {stem_norm}\n")
        for item in save_nodes:
            prefix = item.get('filename_prefix')
            prefix_norm = normalize_name(str(prefix or ''))
            match = bool(prefix_norm and stem_norm.startswith(prefix_norm))
            fh.write(
                f"- {item['source']} node {item['id']}: prefix={prefix!r} | normalized={prefix_norm!r} | startswith_match={match}\n"
            )

    try:
        core_nodes, extra_nodes, summary = parse_nodes(workflow_json or prompt_json)
        write_section(fh, 'Legacy summary from parse_nodes(workflow_json or prompt_json)')
        fh.write(json.dumps(summary, indent=2, ensure_ascii=False))
        fh.write('\n')
        fh.write(f"core_nodes: {len(core_nodes)}\n")
        fh.write(f"third_party_nodes: {len(extra_nodes)}\n")
        if core_nodes:
            fh.write('core node types:\n')
            for node in core_nodes:
                ntype = node.get('class_type') or node.get('type')
                nid = node.get('id', '?')
                fh.write(f"  - {nid}: {ntype}\n")
        if extra_nodes:
            fh.write('third-party/unknown node types:\n')
            for node in extra_nodes:
                ntype = node.get('class_type') or node.get('type')
                nid = node.get('id', '?')
                fh.write(f"  - {nid}: {ntype}\n")
    except Exception as e:
        write_section(fh, 'Legacy summary error')
        fh.write(f'{type(e).__name__}: {e}\n')

    if full_json:
        write_json_block(fh, 'Prompt JSON', prompt_json)
        write_json_block(fh, 'Workflow JSON', workflow_json)


def main():
    ap = argparse.ArgumentParser(description='Dump MBQ-relevant metadata from a PNG test set into a text file.')
    ap.add_argument('input', help='PNG file or directory of PNG files')
    ap.add_argument('-o', '--output', help='Output text file', default='mbq_testset_dump.txt')
    ap.add_argument('--full-json', action='store_true', help='Include full pretty-printed prompt/workflow JSON')
    args = ap.parse_args()

    src = Path(args.input)
    if not src.exists():
        raise SystemExit(f'Input not found: {src}')

    if src.is_file():
        pngs = [src]
        out_path = Path(args.output)
    else:
        pngs = sorted([p for p in src.iterdir() if p.is_file() and p.suffix.lower() == '.png'])
        out_path = src / args.output if not Path(args.output).is_absolute() else Path(args.output)

    if not pngs:
        raise SystemExit('No PNG files found.')

    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write('MBQ TESTSET METADATA DUMP\n')
        fh.write('=========================\n')
        fh.write(f'Input: {src}\n')
        fh.write(f'PNG count: {len(pngs)}\n')
        fh.write(f'Full JSON included: {args.full_json}\n')
        for png in pngs:
            dump_one_png(png, fh, full_json=args.full_json)

    print(f'Wrote: {out_path}')


if __name__ == '__main__':
    main()
