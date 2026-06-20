# ComfyUI-MBQWedge

Three ComfyUI nodes that sweep a parameter across a range, generating one image per value —
analogous to a photographic wedge or exposure bracket.

| Node | Sweeps |
|---|---|
| **MBQ Wedge** | Numeric range (float / int) |
| **MBQ Wedge Sampler** | All sampler names registered in ComfyUI |
| **MBQ Wedge Scheduler** | All (or a named subset of) scheduler names registered in ComfyUI |

## Install

Copy or symlink this `ComfyUI-MBQWedge/` folder into your ComfyUI custom nodes directory:

```
ComfyUI/custom_nodes/ComfyUI-MBQWedge/
```

Restart ComfyUI. All nodes appear under **MBQ** in the node list.

---

## MBQ Wedge — numeric sweep

Add **MBQ Wedge** to your workflow and wire one of its two outputs:

| Output socket | Connect to | Example |
|---|---|---|
| `int_value` | Any INT input | KSampler → steps |
| `float_value` | Any FLOAT input | KSampler → cfg |

ComfyUI greys out incompatible socket types when dragging a link.

### Inputs

| Input | Type | Description |
|---|---|---|
| `parameter_name` | STRING | Auto-filled when you connect an output |
| `start` | FLOAT | First value in the sweep |
| `stop` | FLOAT | Last value (inclusive) |
| `increment` | FLOAT | Step between values |

### Node display

- **will produce → N iterations** — live count of images that will be queued
- **current → X.XX** — starting value (cosmetic; updates as `start` changes)

### Example: sweep steps 10 → 20 by 2

```
start     = 10
stop      = 20
increment = 2
```

Wire `int_value` → KSampler `steps`. Click Queue → 6 separate jobs submitted automatically.

---

## MBQ Wedge Sampler / Scheduler — string sweep

Connect the output to the matching input and click Queue — the node sweeps every value automatically.

Output type matches the KSampler COMBO exactly, so ComfyUI accepts the link. Values come from `comfy.samplers.KSampler.SAMPLERS` / `.SCHEDULERS` — the same live registry ComfyUI itself uses, so any samplers or schedulers added by other custom nodes are included automatically. The list is read at ComfyUI startup; the node label updates immediately.

**MBQ Wedge Sampler / Scheduler** both have an optional **filter** field. Leave it blank to sweep all values, or list names (one per line, or space-separated) to sweep only those. Invalid names (not in your ComfyUI's registry) are silently skipped and the label shows the real count.

| Output socket | Connect to |
|---|---|
| `sampler_name` (Sampler) | KSampler `sampler_name` or equivalent |
| `scheduler` (Scheduler) | KSampler `scheduler` or equivalent |

ComfyUI treats all COMBO sockets as the same generic type, so it's possible to drag a
Scheduler wedge into a `sampler_name` slot (or vice versa) by mistake. MBQ catches this:
the mismatched link is automatically disconnected with a warning, so you can't
accidentally feed the wrong list into a parameter.

### Node display

- **all N samplers → N images** — sweeping the full list
- **N of M schedulers → N images** — sweeping a filtered subset

### Example: sweep all samplers

Add **MBQ Wedge Sampler** → connect `sampler_name` → KSampler `sampler_name`.
Node shows "all 14 samplers → 14 images" (or however many your ComfyUI has).
Click Queue → one job per sampler name submitted automatically.

### Example: sweep a scheduler subset

Add **MBQ Wedge Scheduler** → connect `scheduler` → KSampler `scheduler`.
In the filter field, type one scheduler name per line (e.g. `simple`, `beta`, `normal`).
Node shows "3 of 9 schedulers → 3 images". Click Queue → 3 jobs.

---

## How Queue works

When you click Queue, the MBQ JS extension intercepts the submission and expands it into
N individual jobs — one per sweep value. Each job has the swept value patched into the
node's `inputs.current`, so the PNG produced by each job carries the exact value in its
embedded prompt chunk.

This is the same mechanism ComfyUI uses for per-image seed randomization. Images appear
in the output folder as each job completes.

### Only one wedge can drive a sweep at a time

If more than one MBQ Wedge node is connected to a real parameter at once (e.g. a numeric
wedge wired to `steps` *and* a Scheduler wedge wired to `scheduler`), MBQ shows a warning
toast and **gets out of the way entirely** — it submits one normal Queue job instead of a
sweep. No node is picked as a "winner." The single image renders using whatever each
wedge's widget is currently showing (its static `current` value, or `start` for the
numeric wedge) — exactly as if MBQ weren't installed. Disconnect the extra wedge(s) to
resume sweeping.

---

## MBQ Viewer integration

Open the generated images in [MBQ](https://github.com/Beakfx/mbq). The viewer reads
`inputs.current` and `inputs.parameter_name` from each image's embedded prompt chunk and
overlays the swept parameter and value on the canvas (e.g. `sampler_name: euler`). The
Wedge bulb in the status bar lights when a wedge is detected.

Because the value is embedded in the PNG itself, it remains correct if you move or rename
the file.
