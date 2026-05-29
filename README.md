# MBQ — Meta Browser Qt  ·  MBQ Wedge Node

**MBQ is two companion tools for [ComfyUI](https://github.com/comfyanonymous/ComfyUI) that work best together:**

| | |
|---|---|
| **MBQ Wedge** | A ComfyUI custom node that sweeps any numeric parameter across a range — steps, CFG, guidance, denoise — queuing one image per value with a single click. |
| **MBQ Browser** | An OpenGL-accelerated desktop image viewer that reads ComfyUI's embedded prompt data from each PNG and overlays the swept parameter value directly on the canvas. |

Together they form a tight review loop: sweep a parameter in ComfyUI → open the output folder in MBQ Browser → flip through the results with the swept value labelled on every image.

---

## MBQ Wedge — ComfyUI node

### Install
Copy (or symlink) the `comfy_nodes/` folder into your ComfyUI custom nodes directory and restart ComfyUI:

```
ComfyUI/custom_nodes/ComfyUI-MBQWedge/
```

The node appears under **MBQ → MBQ Wedge**.

### How it works
Add MBQ Wedge to any workflow and wire one output to any numeric input:

| Output | Connect to |
|--------|-----------|
| `int_value` | Any INT input (steps, width, …) |
| `float_value` | Any FLOAT input (CFG, guidance, denoise, …) |

Set `start`, `stop`, and `increment`. Click **Queue once** — the MBQ JS extension intercepts the submission and expands it into N separate jobs automatically, one per sweep value.

Each output PNG has the **exact swept value embedded** in its prompt chunk, so MBQ Browser can read and display it without guessing — even if you rename or move the file.

Seeds advance correctly across sweep jobs (randomize / increment / decrement / fixed all work as configured).

### Example — sweep CFG 3 → 7
```
parameter_name = "cfg"    (auto-filled when you connect the output)
start     = 3.0
stop      = 7.0
increment = 1.0
```
Wire `float_value` → KSampler `cfg`. Click Queue → 5 jobs, 5 PNGs, each labelled `cfg: 3.00` through `cfg: 7.00` in MBQ Browser.

### Node display
- **will produce → N iterations** — live count updates as you adjust the range
- **current → X** — shows the first value; switches to integer display when wired to an INT input

---

## MBQ Browser — desktop viewer

### Install
**Requirements:** Python 3.11+, PySide6

```bash
pip install pyside6
python mbq_browser.py
```

```bash
python mbq_browser.py path/to/image.png   # open image + its folder
python mbq_browser.py path/to/folder/     # open folder
```

### Features

**Canvas**
- OpenGL-accelerated — smooth pan (left-drag), scroll-wheel zoom anchored at cursor
- Middle-click-tap to reset zoom to 100%
- Drag images in from Explorer or ComfyUI; drag thumbnails out to Explorer or ComfyUI

**Zoom modes** (mutually exclusive, each has a status bulb)
| Key | Mode | Bulb |
|-----|------|------|
| `Z` | Zoom Lock — preserve exact transform across image switches | Green |
| `F` | Fit Lock — auto-fit every image to the window | Teal |
| `R` | Reset — 100% zoom, clears both locks | — |

**Metadata panel**
- Three-tier display: **(1)** models, prompts, sampler params — **(2)** other scalars — **(3)** plumbing nodes (collapsible)
- Colour-coded: cyan node headers · yellow keys · near-white values
- **Copy Summary** — plain-text summary for notes or sharing
- **Copy Workflow** — raw LiteGraph JSON for direct re-import into ComfyUI

**MBQ Wedge integration**
- Wedge bulb (blue) lights when a swept image is detected
- Swept parameter and value overlaid on the canvas: `steps: 6`
- Overlay stays fixed in the corner — unaffected by zoom or pan

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+O` | Open image |
| `← / →` | Previous / next image |
| `Z` | Toggle zoom lock |
| `F` | Toggle fit lock |
| `R` | Reset zoom to 100%, clear locks |
| `S` | Toggle scroll freeze |
| `Ctrl+Q` | Quit |

---

## Status bulbs

| Bulb | Colour | Meaning |
|------|--------|---------|
| Wedge | Blue | MBQWedge sweep detected in this image |
| Zoom | Green | Zoom Lock active |
| Fit | Teal | Fit Lock active |
| Scroll | Green | Scroll Freeze active |
| UnComfy | Amber | File may be a preview save, not a final output |

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

- **ComfyUI only.** MBQ reads the `prompt` chunk written by ComfyUI's SaveImage node. It does not support A1111, NovelAI, InvokeAI, or other tools.
- **Soft-fail.** If a PNG has no prompt chunk, MBQ shows the image and leaves the metadata panel blank — it never crashes or shows garbage.
- No ComfyUI runtime dependency — MBQ Browser reads files only.
