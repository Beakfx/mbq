# MBQ Viewer + Wedge Node for ComfyUI

Image viewer and parameter sweep tool for ComfyUI workflows.

[![MBQ Viewer showing a Flux workflow...](assets/screenshot.png)](assets/screenshot.png)

**MBQ Viewer** is a standalone desktop app that reads the prompt data embedded in
every ComfyUI PNG and displays it in a clean, colour-coded panel right alongside
the image — models, prompts, sampler params, all readable without digging into JSON.
Works on any PNG saved by ComfyUI's SaveImage node, not just MBQ Wedge outputs.
ComfyUI doesn't need to be running.

**MBQ Wedge** is a family of three companion ComfyUI nodes that sweep a parameter across a range, queuing one image per value from a single click. Each PNG gets the swept value embedded, so the viewer labels every image automatically. Lock your zoom to a crop and flip through the whole sweep at pixel level.

| Node | Sweeps |
|---|---|
| **MBQ Wedge** | Numeric range (float / int) — steps, CFG, denoise, … |
| **MBQ Wedge Sampler** | All available sampler names |
| **MBQ Wedge Scheduler** | All or a named subset of scheduler names |

**The loop:** get a result you like in ComfyUI → freeze the seed → add an MBQ Wedge node and sweep the parameter you're uncertain about → open the output folder in MBQ Viewer → flip through results with the swept value labelled on every image, zoomed in to the exact detail you care about.

---

## MBQ Wedge — ComfyUI node

### Install

Copy (or symlink) the `ComfyUI-MBQWedge/` folder into your ComfyUI custom nodes directory and restart ComfyUI:

```
ComfyUI/custom_nodes/ComfyUI-MBQWedge/
```

All three nodes appear under **MBQ** in the node list.

### How it works

Each node intercepts the Queue button and expands one click into N separate jobs — one per swept value. Every output PNG has the **exact swept value embedded** in its ComfyUI prompt chunk. MBQ Viewer reads it directly — no guessing, no positional inference. Seeds advance correctly across jobs (randomize / increment / decrement / fixed all work as configured).

**MBQ Wedge (numeric)** — wire one output to any numeric input:

| Output | Connect to |
|--------|-----------|
| `int_value` | Any INT input (steps, width, …) |
| `float_value` | Any FLOAT input (CFG, guidance, denoise, …) |

Set `start`, `stop`, and `increment`. The node shows **will produce → N iterations** live as you adjust the range.

**MBQ Wedge Sampler / Scheduler** — wire the output directly to `sampler_name` or `scheduler` on a KSampler. The output type matches the COMBO exactly so ComfyUI accepts the link. Values come from `comfy.samplers.KSampler.SAMPLERS` / `.SCHEDULERS` — the same live registry ComfyUI uses, so any samplers or schedulers added by other custom nodes are included automatically.

**MBQ Wedge Sampler / Scheduler** both have an optional **filter** field: leave blank to sweep all values, or list names (one per line, or space-separated) to sweep only those. Invalid names (not in your ComfyUI's registry) are silently skipped. The label updates live to show the actual count.

**Only one wedge can drive a sweep at a time.** If more than one MBQ Wedge node is connected to a real parameter at once, MBQ shows a warning and gets out of the way entirely — it queues a single normal job instead of guessing which one should win. The render uses whatever each connected wedge's widget is currently showing, exactly as if MBQ weren't installed. Disconnect the extra wedge(s) to resume sweeping.

### Example — sweep steps 4 → 12

```
parameter_name = "steps"   (auto-filled when you connect the output)
start          = 4
stop           = 12
increment      = 1
```

Wire `int_value` → BasicScheduler `steps`. Click Queue → 9 jobs, 9 PNGs, each labelled `steps: 4` through `steps: 12` in MBQ Viewer.

### Example — sweep all samplers

Add **MBQ Wedge Sampler** → connect `sampler_name` output → KSampler `sampler_name`. Click Queue → one job per sampler, each PNG labelled `sampler_name: euler` etc.

### Example — sweep a scheduler subset

Add **MBQ Wedge Scheduler** → connect `scheduler` output → KSampler `scheduler`. In the filter field type one scheduler name per line. Node label shows **3 of 9 schedulers → 3 images**. Click Queue → 3 jobs.

---

## MBQ Viewer — desktop viewer

### Install

**Option A — Windows installer**

Download `MBQViewer-Setup-1.2.0.exe` from the **[Releases page](https://github.com/Beakfx/mbq/releases)** and run it. Installs to `Program Files\MBQ Viewer`, adds a Start Menu entry, and optionally a desktop shortcut. Uninstall via Windows Settings → Apps.

> **Windows SmartScreen:** MBQ Viewer is not yet code-signed, so Windows may show a "Windows protected your PC" dialog. Click **More info → Run anyway**. This is normal for unsigned indie software.

**Option B — portable exe (Windows)**

Download `MBQViewer.exe` from the **[Releases page](https://github.com/Beakfx/mbq/releases)**. No install required — just run it from anywhere. Startup is a few seconds slower than the installer version because it unpacks itself to a temp folder on each launch.

> Same SmartScreen note applies.

**Option C — run from source (Windows / Linux / Mac)**

**Requirements:** Python 3.11+

```bash
git clone https://github.com/Beakfx/mbq.git
cd mbq
pip install -r requirements.txt
python mbq_viewer.py
```

Drag images in from Explorer or ComfyUI. Drag thumbnails out to Explorer or ComfyUI.

### Canvas

- OpenGL-accelerated — smooth pan (left-drag), scroll-wheel zoom anchored at cursor
- Middle-click to reset zoom to 100%
- **Zoom Lock (`Z`)** — preserves the exact pan and zoom position when flipping between images, so you can inspect the same crop across an entire sweep
- **Fit Lock (`F`)** — auto-fits every image to the window; persists through window resizes and fullscreen toggle
- **Reset (`R`)** — 100% zoom, clears both locks
- **Full Screen (`F11`)** — canvas-only view, all chrome hidden; `Esc` or `F11` to exit

### Workflow panel

Reads the prompt JSON embedded by ComfyUI's SaveImage node and displays it in a colour-coded panel:

- **Tier 1** — models, prompts, sampler params (the things you usually care about)
- **Tier 2** — other scalar values
- **Tier 3** — plumbing nodes (expandable, hidden by default)

Colour coding: cyan node headers · yellow keys · near-white values

**Copy Summary** — plain-text summary for notes or sharing  
**Copy Workflow** — raw LiteGraph JSON for direct re-import into ComfyUI

**Scroll Freeze (`S`)** — locks the workflow panel's scroll position when flipping between images, so the same section of the metadata stays in view across an entire sweep.

### MBQ Wedge integration

When a swept image is loaded, MBQ Viewer:
- Lights the **Wedge bulb** (blue) in the status bar
- Overlays the swept parameter and value on the canvas corner: `steps: 6` or `sampler_name: euler`
- Highlights the swept value in the Workflow panel's wedge node entry

Works with all three wedge node types. The overlay is fixed to the canvas corner — unaffected by zoom, pan, or fullscreen mode.

### Culling images

Press `Delete` (or the **Delete** button in the toolbar) to move the current image to the OS trash — Recycle Bin on Windows, Trash on macOS, XDG trash on Linux. The viewer advances to the next image automatically.

**Multi-select:** Shift-click a thumbnail in the filmstrip to select a range, or Ctrl-click to toggle individual thumbnails in or out of the selection (in any order). Pressing `Delete` with multiple thumbnails selected deletes all of them at once (with a confirmation).

Press `Ctrl+Z` (or **Edit → Restore Deleted**) to restore the last deleted image — or the entire last batch, if you deleted a multi-selection. Multiple undo levels are supported within the same folder session. If you switch folders and then undo, the file is still restored on disk — navigate back to that folder to find it.

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
| `F11` | Enter / exit full screen |
| `Esc` | Exit full screen |
| `Ctrl+Q` | Quit |

The **Search** box above the workflow panel highlights all matching text across the workflow panel. The search term persists when flipping between images — useful for comparing the same parameter across a sweep. Scroll Freeze is respected: if active, the panel won't jump to the first match.

---

## Status bulbs

| Bulb | Colour | Meaning |
|------|--------|---------|
| Wedge | Blue | MBQ Wedge sweep detected in this image (any of the three node types) |
| Zoom | Green | Zoom Lock active |
| Fit | Teal | Fit Lock active |
| Scroll | Green | Scroll Freeze active |
| UnComfy | Amber | Workflow data may not be trustworthy — see below |

**UnComfy** lights when MBQ Viewer has reason to doubt the workflow panel reflects what
actually generated the image. Possible causes: the file is not a ComfyUI PNG at all,
it was renamed (breaking the embedded path), it's a preview save rather than a final
output, or the `prompt` chunk parsed but looked structurally odd. It's a prompt to be
sceptical, or 'uncomfortable' — the image is shown as-is, but treat any displayed parameters with caution.

---

## File map

| File | Role |
|------|------|
| `mbq_viewer.py` | Main window — layout, menus, navigation, metadata display, filmstrip |
| `mbq_functions.py` | `ImageCanvas` (OpenGL view), `ImageFolder`, `WorkflowCache` |
| `mbq_parser.py` | PNG chunk extraction, ComfyUI prompt graph parsing, three-tier node classification |
| `ComfyUI-MBQWedge/mbq_wedge.py` | All three MBQ Wedge node classes |
| `ComfyUI-MBQWedge/__init__.py` | Node registration |
| `ComfyUI-MBQWedge/js/mbq_wedge.js` | JS extension: widgets, queue intercept, seed handling |

---

## Notes

- **ComfyUI only.** MBQ reads the `prompt` chunk written by ComfyUI's SaveImage node. A1111, NovelAI, InvokeAI, and other tools are not supported.
- **Soft-fail.** If a PNG has no prompt chunk, MBQ shows the image and leaves the workflow panel blank — it never crashes or shows garbage.
- **No ComfyUI runtime dependency.** MBQ Viewer reads PNG files directly; ComfyUI does not need to be running.
- **Cross-platform.** Developed on Windows; should work on Linux. Mac support is untested.

---

**[github.com/Beakfx/mbq](https://github.com/Beakfx/mbq)**
