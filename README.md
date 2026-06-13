# MBQ Viewer + Wedge Node for ComfyUI

Image viewer and parameter sweep tool for ComfyUI workflows.

[![MBQ Viewer showing a Flux workflow...](assets/screenshot.png)](assets/screenshot.png)

**MBQ Viewer** is a standalone desktop app that reads the prompt data embedded in
every ComfyUI PNG and displays it in a clean, colour-coded panel right alongside
the image — models, prompts, sampler params, all readable without digging into JSON.
Works on any PNG saved by ComfyUI's SaveImage node, not just MBQ Wedge outputs.
ComfyUI doesn't need to be running.

**MBQ Wedge** is a companion ComfyUI node that sweeps any numeric parameter
across a range — steps, CFG, denoise, anything — queuing one image per value
from a single click. Each PNG gets the swept value embedded, so the viewer
labels every image automatically. Lock your zoom to a crop and flip through
the whole sweep at pixel level.

**The loop:** get a result you like in ComfyUI → freeze the seed → add MBQ Wedge and sweep the parameter you're uncertain about → open the output folder in MBQ Viewer → flip through results with the swept value labelled on every image, zoomed in to the exact detail you care about.

---

## MBQ Wedge — ComfyUI node

### Install

Copy (or symlink) the `ComfyUI-MBQWedge/` folder into your ComfyUI custom nodes directory and restart ComfyUI:

```
ComfyUI/custom_nodes/ComfyUI-MBQWedge/
```

The node appears under **MBQ → MBQ Wedge**.

### How it works

Add MBQ Wedge to any workflow and wire one output to a numeric input:

| Output | Connect to |
|--------|-----------|
| `int_value` | Any INT input (steps, width, …) |
| `float_value` | Any FLOAT input (CFG, guidance, denoise, …) |

Set `start`, `stop`, and `increment`. Click **Queue once** — the MBQ JS extension intercepts the submission and expands it into N separate jobs, one per sweep value.

Each output PNG has the **exact swept value embedded** in its ComfyUI prompt chunk. MBQ Viewer reads it directly — no guessing, no positional inference. Works correctly across multiple batches and renamed files.

Seeds advance correctly across sweep jobs: randomize, increment, decrement, and fixed modes all work as configured.

### Node display

- **will produce → N iterations** — live count updates as you adjust the range
- **current → X** — shows the starting value; switches to integer display when wired to an INT input

### Example — sweep steps 4 → 12

```
parameter_name = "steps"   (auto-filled when you connect the output)
start          = 4
stop           = 12
increment      = 1
```

Wire `int_value` → BasicScheduler `steps`. Click Queue → 9 jobs, 9 PNGs, each labelled `steps: 4` through `steps: 12` in MBQ Viewer.

---

## MBQ Viewer — desktop viewer

### Install

**Option A — Windows installer**

Download `MBQViewer-Setup-1.0.0.exe` from the **[Releases page](https://github.com/Beakfx/mbq/releases)** and run it. Installs to `Program Files\MBQ Viewer`, adds a Start Menu entry, and optionally a desktop shortcut. Uninstall via Windows Settings → Apps.

> **Windows SmartScreen:** MBQ Viewer is not yet code-signed, so Windows may show a "Windows protected your PC" dialog. Click **More info → Run anyway**. This is normal for unsigned indie software.

**Option B — portable exe (Windows)**

Download `MBQViewer.exe` from the **[Releases page](https://github.com/Beakfx/mbq/releases)**. No install required — just run it from anywhere. Startup is a few seconds slower than the installer version because it unpacks itself to a temp folder on each launch.

> Same SmartScreen note applies.

**Option C — run from source (Windows / Linux / Mac)**

**Requirements:** Python 3.11+

```bash
git clone https://github.com/Beakfx/mbq.git
cd mbq
pip install pyside6 send2trash
python mbq_viewer.py
```

Drag images in from Explorer or ComfyUI. Drag thumbnails out to Explorer or ComfyUI.

### Canvas

- OpenGL-accelerated — smooth pan (left-drag), scroll-wheel zoom anchored at cursor
- Middle-click to reset zoom to 100%
- **Zoom Lock (`Z`)** — preserves the exact pan and zoom position when flipping between images, so you can inspect the same crop across an entire sweep
- **Fit Lock (`F`)** — auto-fits every image to the window
- **Reset (`R`)** — 100% zoom, clears both locks

### Workflow panel

Reads the prompt JSON embedded by ComfyUI's SaveImage node and displays it in a colour-coded panel:

- **Tier 1** — models, prompts, sampler params (the things you usually care about)
- **Tier 2** — other scalar values
- **Tier 3** — plumbing nodes (collapsible, hidden by default)

Colour coding: cyan node headers · yellow keys · near-white values

**Copy Summary** — plain-text summary for notes or sharing  
**Copy Workflow** — raw LiteGraph JSON for direct re-import into ComfyUI

**Scroll Freeze (`S`)** — locks the workflow panel's scroll position when flipping between images, so the same section of the metadata stays in view across an entire sweep.

### MBQ Wedge integration

When a swept image is loaded, MBQ Viewer:
- Lights the **Wedge bulb** (blue) in the status bar
- Overlays the swept parameter and value on the canvas corner: `steps: 6`
- Highlights the swept value in the Workflow panel's MBQWedge entry

The overlay is fixed to the canvas corner — unaffected by zoom or pan.

### Culling images

Press `Delete` (or the **Delete** button in the toolbar) to move the current image to the OS trash — Recycle Bin on Windows, Trash on macOS, XDG trash on Linux. The viewer advances to the next image automatically.

Press `Ctrl+Z` (or **Edit → Restore Deleted**) to restore the last deleted image from trash. Multiple undo levels are supported within the same folder session. If you switch folders and then undo, the file is still restored on disk — navigate back to that folder to find it.

> **Network shares:** if the file is on a network share or filesystem that doesn't support trash, MBQ Viewer will ask before permanently deleting. Undo is not available for permanent deletes.

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+O` | Open image |
| `← / →` | Previous / next image |
| `Delete` | Move current image to Recycle Bin / Trash |
| `Ctrl+Z` | Restore last deleted image |
| `F5` | Refresh folder |
| `Z` | Toggle zoom lock |
| `F` | Toggle fit lock |
| `R` | Reset zoom to 100%, clear locks |
| `S` | Toggle scroll freeze |
| `Ctrl+Q` | Quit |

The **Search** box above the workflow panel highlights all matching text across the workflow panel. The search term persists when flipping between images — useful for comparing the same parameter across a sweep. Scroll Freeze is respected: if active, the panel won't jump to the first match.

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
| `mbq_viewer.py` | Main window — layout, menus, navigation, metadata display, filmstrip |
| `mbq_functions.py` | `ImageCanvas` (OpenGL view), `ImageFolder`, `WorkflowCache` |
| `mbq_parser.py` | PNG chunk extraction, ComfyUI prompt graph parsing, three-tier node classification |
| `ComfyUI-MBQWedge/mbq_wedge.py` | MBQWedge ComfyUI node |
| `ComfyUI-MBQWedge/js/mbq_wedge.js` | JS extension: widgets, queue intercept, seed handling |

---

## Notes

- **ComfyUI only.** MBQ reads the `prompt` chunk written by ComfyUI's SaveImage node. A1111, NovelAI, InvokeAI, and other tools are not supported.
- **Soft-fail.** If a PNG has no prompt chunk, MBQ shows the image and leaves the workflow panel blank — it never crashes or shows garbage.
- **No ComfyUI runtime dependency.** MBQ Viewer reads PNG files directly; ComfyUI does not need to be running.
- **Cross-platform.** Developed on Windows; should work on Linux. Mac support is untested.

---

**[github.com/Beakfx/mbq](https://github.com/Beakfx/mbq)**
