# ComfyUI-MBQWedge

A single ComfyUI node that sweeps a numeric parameter across a range, generating one
image per value in a queue run — analogous to a photographic wedge or exposure bracket.

## Install (local / Phase 1)

Copy or symlink this `comfy_nodes/` folder into your ComfyUI custom nodes directory:

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
| `parameter_name` | STRING | Name of the swept parameter (e.g. `"steps"`, `"cfg"`). MBQ reads this to label the canvas overlay. |
| `start` | FLOAT | First value in the sweep |
| `step_size` | FLOAT | Increment between values |
| `stop` | FLOAT | Last value (inclusive) |

### Example: sweep steps 10 → 20 by 2

```
parameter_name = "steps"
start     = 10
step_size = 2
stop      = 20
```

Wire `int_value` → KSampler `steps`. Queue once → 6 images generated, one per value.

### Example: sweep CFG 1.0 → 7.0 by 1.5

```
parameter_name = "cfg"
start     = 1.0
step_size = 1.5
stop      = 7.0
```

Wire `float_value` → KSampler `cfg`. Queue once → 5 images generated.

### Important: let all iterations finish

ComfyUI runs all samplers first, then all decoders, then all save/preview nodes —
it does not produce output after each individual iteration. **Do not interrupt the
queue mid-run.** All images appear at the end once the full sweep completes.

## MBQ Viewer integration

Open the generated images in [MBQ](https://github.com/Beakfx/mbq). The viewer detects
the wedge node in each image's embedded prompt and overlays the swept parameter and its
current value directly on the canvas (e.g. `cfg: 3.5`). The Wedge bulb in the status
bar lights green when a wedge is detected.
