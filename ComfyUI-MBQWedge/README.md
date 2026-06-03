# ComfyUI-MBQWedge

A single ComfyUI node that sweeps a numeric parameter across a range, generating one
image per value — analogous to a photographic wedge or exposure bracket.

## Install (local / Phase 1)

Copy or symlink this `ComfyUI-MBQWedge/` folder into your ComfyUI custom nodes directory:

```
ComfyUI/custom_nodes/ComfyUI-MBQWedge/
```

Restart ComfyUI. The node appears in the node list under **MBQ → MBQ Wedge**.

## Usage

Add **MBQ Wedge** to your workflow and wire one of its two outputs:

| Output socket | Connect to | Example |
|---|---|---|
| `int_value` | Any INT input | KSampler → steps |
| `float_value` | Any FLOAT input | KSampler → cfg |

ComfyUI greys out incompatible socket types when dragging a link, so you can only
connect the right type for the target parameter.

### Inputs

| Input | Type | Description |
|---|---|---|
| `parameter_name` | STRING | Name of the swept parameter (auto-filled when you connect an output). |
| `start` | FLOAT | First value in the sweep |
| `stop` | FLOAT | Last value (inclusive) |
| `increment` | FLOAT | Step between values |

### Node display widgets

- **will produce → N iterations** — live count of images that will be queued
- **current → X.XX** — the first iteration's value (cosmetic; updates as `start` changes)

### Example: sweep steps 10 → 20 by 2

```
parameter_name = "steps"
start     = 10
stop      = 20
increment = 2
```

Wire `int_value` → KSampler `steps`. Click Queue → 6 separate jobs submitted automatically.

### Example: sweep CFG 1.0 → 7.0 by 1.5

```
parameter_name = "cfg"
start     = 1.0
stop      = 7.0
increment = 1.5
```

Wire `float_value` → KSampler `cfg`. Click Queue → 5 separate jobs submitted automatically.

## How Queue works with MBQWedge

When you click Queue, the MBQ JS extension intercepts the submission and expands it into
N individual jobs — one per sweep value. Each job has the swept value patched directly
into MBQWedge's inputs (`start=V, stop=V, current=V`), so the PNG produced
by each job carries the exact value in its embedded prompt chunk.

This is the same mechanism ComfyUI uses for per-image seed randomization.

Images appear in the output folder as each job completes — you don't need to wait for
the full sweep before results start appearing.

## MBQ Viewer integration

Open the generated images in [MBQ](https://github.com/Beakfx/mbq). The viewer reads
`MBQWedge.inputs.current` from each image's embedded prompt chunk and overlays the swept
parameter and its value directly on the canvas (e.g. `cfg: 3.5`). The Wedge bulb in the
status bar lights green when a wedge is detected.

Because the value is embedded in the PNG itself, it remains correct if you move or rename
the file.
