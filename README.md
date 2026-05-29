# MBQ — Meta Browser Qt

An OpenGL-accelerated image browser built for [ComfyUI](https://github.com/comfyanonymous/ComfyUI) workflows. MBQ reads the `prompt` JSON that ComfyUI's SaveImage node embeds in every PNG and displays generation parameters — model, prompts, sampler, CFG, seed, steps, scheduler — in a colour-coded side panel.

---

## Features

### Image browser
- OpenGL-accelerated canvas — smooth pan (left-drag), scroll-wheel zoom anchored at cursor, middle-click-tap to reset
- **Zoom Lock** (`Z`) — preserve exact transform across image switches for direct A/B comparison
- **Fit Lock** (`F`) — auto-fit every image to the window; useful for mixed-resolution folders
- **Reset** (`R`) — 100% zoom, clears both locks
- **Scroll Freeze** (`S`) — keeps the metadata panel scroll position while flipping images
- Filmstrip thumbnail strip with wraparound; green border on current image
- Drag an image out of the filmstrip to Explorer, ComfyUI, or any drop target
- Drag an image file in to open it

### Metadata panel
- Three-tier display: **(1)** models, prompts, sampler params — **(2)** other node scalars — **(3)** plumbing nodes (collapsible)
- Colour-coded: cyan node headers · yellow keys · near-white values
- Filename highlighted amber when the file looks like a ComfyUI preview save
- **Copy Summary** — plain-text summary of file info and generation params
- **Copy Workflow** — raw LiteGraph JSON for direct re-import into ComfyUI

### Status bulbs
| Bulb | Colour | Meaning |
|------|--------|---------|
| Wedge | Blue | MBQWedge node detected in this image |
| Zoom | Green | Zoom Lock active |
| Fit | Teal | Fit Lock active |
| Scroll | Green | Scroll Freeze active |
| UnComfy | Amber | Image may be a preview save, not a final output |

---

## MBQ Wedge — companion ComfyUI node

The **MBQ Wedge** node sweeps any numeric parameter across a range, queuing one job per value — like a photographic exposure bracket.

### Install
Copy (or symlink) the `comfy_nodes/` folder into your ComfyUI custom nodes directory and restart ComfyUI:

```
ComfyUI/custom_nodes/ComfyUI-MBQWedge/
```

The node appears in the node list under **MBQ → MBQ Wedge**.

### How it works
Wire one output to any numeric input on any node:

| Output | Connect to |
|--------|-----------|
| `int_value` | Any INT input (steps, width, …) |
| `float_value` | Any FLOAT input (CFG, guidance, denoise, …) |

Set `start`, `stop`, and `increment`. Click **Queue once** — the MBQ JS extension intercepts the submission and fans it out into N separate jobs automatically, one per sweep value.

Each output PNG has its **exact swept value embedded** in the prompt chunk (`MBQWedge.inputs.current`), so MBQ can read and display it without guessing:
- Canvas overlay: `steps: 6`
- Metadata panel: `current` field in the MBQWedge block
- Wedge bulb lights blue

Seeds advance correctly across sweep jobs (randomize / increment / decrement / fixed all work as configured).

### Example — sweep steps 4 → 8
```
parameter_name = "steps"   (auto-filled on connect)
start     = 4
stop      = 8
increment = 1
```
Wire `int_value` → KSampler `steps`. Click Queue → 5 separate jobs submitted, 5 PNGs produced, each labelled with its step count.

---

## Installation

**Requirements:** Python 3.11+, PySide6

```bash
pip install pyside6
```

**Run:**
```bash
python mbq_browser.py                      # open blank
python mbq_browser.py path/to/image.png    # open image + its folder
python mbq_browser.py path/to/folder/      # open folder
```

---

## Keyboard shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+O` | Open image |
| `← / →` | Previous / next image |
| `Z` | Toggle zoom lock |
| `F` | Toggle fit lock (auto-fit each image) |
| `R` | Reset zoom to 100%, clear locks |
| `S` | Toggle scroll freeze |
| `Ctrl+Q` | Quit |

---

## File map

| File | Role |
|------|------|
| `mbq_browser.py` | Main window — layout, menus, status bulbs |
| `mbq_logic.py` | Navigation, metadata display, filmstrip, wedge inference |
| `mbq_functions.py` | `ImageCanvas` (OpenGL view), `ImageFolder`, `WorkflowCache` |
| `mbq_parser.py` | PNG chunk extraction, ComfyUI prompt graph parsing |
| `comfy_nodes/mbq_wedge.py` | MBQWedge ComfyUI node |
| `comfy_nodes/js/mbq_wedge.js` | JS extension: widgets, queue intercept, seed handling |
| `dump_png_text_chunks.py` | CLI debug tool: dump raw PNG text chunks |

---

## Notes

- **ComfyUI only.** MBQ reads the `prompt` chunk written by ComfyUI's SaveImage node. It does not handle A1111, NovelAI, InvokeAI, or other tools.
- **Soft-fail.** If a PNG has no prompt chunk, MBQ shows the image and leaves the metadata panel blank — it never crashes or shows garbage.
- No ComfyUI runtime dependency — MBQ reads files only.
