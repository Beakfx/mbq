# MBQ — Meta Browser Qt

## What this is

MBQ is a PySide6 image file browser for ComfyUI-generated images. It reads the `prompt`
JSON embedded by ComfyUI's SaveImage node into PNG text chunks and displays generation
parameters (model, prompts, sampler, CFG, seed, scheduler) in a side panel.

## Scope — read this first

**ComfyUI only.** Do not add handling for A1111, NovelAI, InvokeAI, or any other tool.
Previous attempts to cover every genAI system caused the mess this rewrite is cleaning up.

**Soft-fail always.** If a PNG has no `prompt` chunk, or parsing fails for any reason,
show the image and leave metadata fields blank. Never crash, never show garbage data.

**`prompt` chunk only.** ComfyUI saves two chunks: `"prompt"` (the node graph) and
`"workflow"` (full editor state). Parse only `"prompt"`. The `"workflow"` chunk is
too complex and was the root cause of prior pain — ignore it entirely.

## File map

| File | Role |
|------|------|
| `mbq_layout.py` | Main `MetaViewApp` window — PySide6 QMainWindow, UI layout |
| `mbq_logic.py` | `MetaViewLogicMixin` — image navigation, metadata display, file dialog |
| `mbq_functions.py` | `ImageFolder`, `ImageCanvas` (QGraphicsView), `WorkflowCache` |
| `mbq_parser.py` | `digest_workflow()` — PNG chunk extraction + ComfyUI prompt graph traversal |
| `mbq_metadata.py` | `ImageMetadata` dataclass — unified structure for all extracted fields |
| `mbq_nodes.py` | Static ComfyUI node registry (Jan 2025 snapshot) — used by CLI tools only |
| `dump_png_text_chunks.py` | CLI: dump raw PNG text chunks for debugging |
| `mbq_audit_current_logic.py` | CLI: audit parser decisions on a batch of PNGs |
| `mbq_dump_testset.py` | CLI: generate metadata reports from a test image set |

## Architecture

```
MetaViewApp (mbq_layout.py)
  ├─ MetaViewLogicMixin (mbq_logic.py)
  │     └─ digest_workflow() ← mbq_parser.py
  │           └─ ImageMetadata ← mbq_metadata.py
  ├─ ImageCanvas, ImageFolder, WorkflowCache (mbq_functions.py)
  └─ [mbq_nodes.py — CLI audit tools only, not used by the GUI]
```

## PNG chunk format

ComfyUI's SaveImage node writes JSON into PNG text chunks under the key `"prompt"`.
Three chunk types may carry it:

- `tEXt` — plain `key\x00value`
- `zTXt` — `key\x00\x00` + zlib-compressed value
- `iTXt` — `key\x00flags\x00lang\x00translated\x00value`, optionally zlib-compressed

The `prompt` value is a JSON object keyed by node ID. Each node has `class_type`,
`inputs`, and optionally `_meta` (which carries the user-assigned `title` label).

## Tech stack

- Python 3.11+, PySide6 (Qt for Python)
- No ComfyUI runtime dependency — reads files only
- `ImageCanvas` uses QGraphicsView with OpenGL for hardware-accelerated display

## Future: wedge node

A custom ComfyUI node will be built (separately) to let users embed selected parameters
into their workflow. It will appear as a normal node inside the `prompt` JSON. MBQ will
find it by matching `class_type` or `_meta.title` — no separate metadata channel.

Until that node exists, extract parameters from standard ComfyUI nodes already in the
prompt graph (KSampler, CheckpointLoaderSimple, CLIPTextEncode, etc.).

## Dev workflow

```
# Run the GUI
python mbq_layout.py

# Inspect raw chunks in a PNG before debugging the parser
python dump_png_text_chunks.py <file.png>

# Batch-audit parser decisions against a folder of test images
python mbq_audit_current_logic.py <image_dir>
```

No formal test runner exists. Test images are stored under `project_docs/`.
