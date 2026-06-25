import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";
import { ComfyWidgets } from "/scripts/widgets.js";

function updateIterations(node) {
    if (node._mbqUpdating) return;
    node._mbqUpdating = true;
    try {
        const get = name => parseFloat(node.widgets?.find(w => w.name === name)?.value) || 0;
        const start = get("start");
        const step  = get("increment");
        const stop  = get("stop");
        const count = step > 0 ? Math.max(0, Math.floor((stop - start) / step) + 1) : 0;
        const lbl   = node.widgets?.find(w => w.name === "_iterations");
        if (lbl) lbl.value = `${count} iteration${count !== 1 ? "s" : ""}`;
    } finally {
        node._mbqUpdating = false;
    }
}

function updateCurrent(node) {
    if (node._mbqUpdating) return;
    const w   = node.widgets?.find(w => w.name === "start");
    const cur = node.widgets?.find(w => w.name === "_current");
    if (!w || !cur) return;
    const v = parseFloat(w.value);
    if (isNaN(v)) { cur.value = "—"; return; }
    cur.value = node._mbqIsInt ? String(Math.round(v)) : v.toFixed(2);
}

// Rebuild the three numeric widgets as genuine INT or FLOAT widgets using
// ComfyUI's own factory (ComfyWidgets.INT / .FLOAT). This gives native arrow
// stepping, precision and slider feel for the connected type — instead of
// mutating a live FLOAT widget's options (which desyncs the reactive binding
// and breaks the arrows). Each rebuilt widget is spliced back into its original
// index so saved workflows deserialize values into the right slots.
const MBQ_NUMS = ["start", "stop", "increment"];

function rebuildNumberWidgets(node, mode) {
    const type = mode === "int" ? "INT" : "FLOAT";
    for (const name of MBQ_NUMS) {
        const old = node.widgets?.find(w => w.name === name);
        if (!old) continue;
        const idx = node.widgets.indexOf(old);

        let val = parseFloat(old.value);
        if (isNaN(val)) val = 0;
        if (mode === "int") val = Math.round(val);
        const min = (name === "increment") ? (mode === "int" ? 1 : 0.001) : -99999;
        // FLOAT precision is derived from step (precision = -floor(log10(step))).
        // increment uses 0.05 → precision 2, so values like 0.05 are typeable;
        // start/stop keep 0.1 → precision 1 for coarser arrow stepping.
        const step = mode === "int" ? 1 : (name === "increment" ? 0.05 : 0.1);

        node.widgets.splice(idx, 1);   // drop old widget
        const res = ComfyWidgets[type](node, name, [type, { default: val, min, max: 99999, step }], app);
        const w = res.widget;

        const appended = node.widgets.indexOf(w);   // factory pushed it to the end
        if (appended !== -1) node.widgets.splice(appended, 1);
        node.widgets.splice(idx, 0, w);             // restore original position
        w.value = val;

        const orig = w.callback;
        w.callback = function(...args) {
            orig?.apply(this, args);
            updateIterations(node);
            updateCurrent(node);
        };
    }
    node.setDirtyCanvas?.(true, true);
}

function updateWidgetMode(node, isInt) {
    node._mbqIsInt = !!isInt;
    const mode = isInt ? "int" : "float";
    // The Python node already creates FLOAT widgets, so the initial float state
    // needs no rebuild — just record it. Only rebuild on an actual mode change.
    if (node._mbqWidgetMode === undefined && mode === "float") {
        node._mbqWidgetMode = "float";
        return;
    }
    if (node._mbqWidgetMode === mode) return;
    node._mbqWidgetMode = mode;
    rebuildNumberWidgets(node, mode);
}

const STR_WEDGE_TYPES = ["MBQWedgeSampler", "MBQWedgeScheduler"];

app.registerExtension({
    name: "MBQ.Wedge",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        // ── Numeric wedge ────────────────────────────────────────────────────
        if (nodeData.name === "MBQWedge") {
            nodeType.prototype.onNodeCreated = function() {
                const lbl = this.addWidget("custom", "_iterations", "—", () => {}, { serialize: false });
                lbl.draw = function(ctx, node, widget_width, y, H) {
                    ctx.save();
                    ctx.font = "italic 13px Arial";
                    ctx.fillStyle = "#ddd";
                    ctx.textBaseline = "middle";
                    ctx.fillText(`will produce ${this.value}`, 6, y + H / 2);
                    ctx.restore();
                };
                lbl.mouse = () => false;

                const cur = this.addWidget("custom", "_current", "—", () => {}, { serialize: false });
                cur.draw = function(ctx, node, widget_width, y, H) {
                    ctx.save();
                    ctx.font = "italic 13px Arial";
                    ctx.fillStyle = "#aaa";
                    ctx.textBaseline = "middle";
                    ctx.fillText(`current ${this.value}`, 6, y + H / 2);
                    ctx.restore();
                };
                cur.mouse = () => false;

                for (const name of ["start", "stop", "increment"]) {
                    const w = this.widgets?.find(w => w.name === name);
                    if (w) {
                        const orig = w.callback;
                        const node = this;
                        w.callback = function(...args) {
                            orig?.apply(this, args);
                            updateIterations(node);
                            updateCurrent(node);
                        };
                    }
                }
                updateWidgetMode(this, (this.outputs?.[0]?.links?.length ?? 0) > 0);
                updateIterations(this);
                updateCurrent(this);
            };

            nodeType.prototype.onConnectionsChange = function(type, slot, connected, link_info) {
                if (connected && link_info && !this._mbqDisconnecting) {
                    const graph = app.graph;
                    if (graph) {
                        // Auto-fill parameter_name from the connected target slot
                        const targetNode = graph.getNodeById(link_info.target_id);
                        const slotName = targetNode?.inputs?.[link_info.target_slot]?.name;
                        if (slotName) {
                            const w = this.widgets?.find(w => w.name === "parameter_name");
                            if (w) w.value = slotName;
                        }

                        // Disconnect the other output — INT and FLOAT are mutually exclusive
                        const newSlot = link_info.origin_slot;
                        if (newSlot === 0 || newSlot === 1) {
                            const otherSlot = 1 - newSlot;
                            if (this.outputs?.[otherSlot]?.links?.length > 0) {
                                this._mbqDisconnecting = true;
                                this.disconnectOutput(otherSlot);
                                this._mbqDisconnecting = false;
                            }
                        }
                    }
                }
                const isInt = (connected && link_info)
                    ? link_info.origin_slot === 0
                    : (this.outputs?.[0]?.links?.length ?? 0) > 0;
                updateWidgetMode(this, isInt);
                updateIterations(this);
                app.graph?.setDirtyCanvas(true, true);
            };

            return;
        }

        // ── String wedge (Sampler / Scheduler) ───────────────────────────────
        if (!STR_WEDGE_TYPES.includes(nodeData.name)) return;

        nodeType.prototype.onNodeCreated = function () {
            const lbl = this.addWidget("custom", "_iterations", "—", () => {}, { serialize: false });
            lbl.draw = function (ctx, node, widget_width, y, H) {
                ctx.save();
                ctx.font = "italic 13px Arial";
                ctx.fillStyle = "#ddd";
                ctx.textBaseline = "middle";
                ctx.fillText(`will sweep ${this.value}`, 6, y + H / 2);
                ctx.restore();
            };
            lbl.mouse = () => false;

            const kind = nodeData.name === "MBQWedgeSampler" ? "samplers" : "schedulers";
            const currentWidget = this.widgets?.find(w => w.name === "current");
            const allValues = currentWidget?.options?.values ?? [];
            this._mbqAllValues = allValues;
            this._mbqStringValues = allValues;

            const updateLabel = () => {
                const n = this._mbqStringValues.length;
                const total = allValues.length;
                lbl.value = n === total
                    ? `all ${n} ${kind} → ${n} images`
                    : `${n} of ${total} ${kind} → ${n} images`;
            };
            updateLabel();

            // Optional filter textarea: leave blank to sweep all, or list names
            // separated by newlines and/or spaces to sweep only those (matches
            // the space-separated text MBQ Viewer's metadata panel copies out).
            // Invalid names are silently skipped.
            const filterWidget = this.widgets?.find(w => w.name === "filter");
            if (filterWidget) {
                const validSet = new Set(allValues);
                const updateFromFilter = () => {
                    const lines = (filterWidget.value ?? "")
                        .split(/\s+/).map(s => s.trim()).filter(Boolean);
                    this._mbqStringValues = lines.length === 0
                        ? allValues
                        : lines.filter(l => validSet.has(l));
                    updateLabel();
                };
                updateFromFilter();
                const orig = filterWidget.callback;
                filterWidget.callback = function (...args) {
                    orig?.apply(this, args);
                    updateFromFilter();
                };
            }
        };

        // Auto-fill parameter_name from the connected target slot name. Also
        // guards against ComfyUI's generic COMBO typing: a sampler-name COMBO
        // and a scheduler-name COMBO both report the same link type, so the
        // frontend happily lets you wire a Scheduler wedge into a sampler_name
        // input (or vice versa). Compare the target widget's actual accepted
        // values against our own list; if they don't match, undo the link.
        nodeType.prototype.onConnectionsChange = function (type, slot, connected, link_info) {
            if (connected && link_info && !this._mbqDisconnecting) {
                const targetNode   = app.graph?.getNodeById(link_info.target_id);
                const slotName     = targetNode?.inputs?.[link_info.target_slot]?.name;
                const targetWidget = targetNode?.widgets?.find(w => w.name === slotName);
                const targetValues = targetWidget?.options?.values;
                const ours = this._mbqAllValues ?? [];
                const matches = Array.isArray(targetValues)
                    && targetValues.length === ours.length
                    && targetValues.every((v, i) => v === ours[i]);

                if (!matches) {
                    this._mbqDisconnecting = true;
                    this.disconnectOutput(link_info.origin_slot);
                    this._mbqDisconnecting = false;
                    const kind = nodeData.name === "MBQWedgeSampler" ? "samplers" : "schedulers";
                    const msg = `"${slotName ?? "that input"}" doesn't take ${kind} — connection removed.`;
                    app.extensionManager?.toast?.add?.({
                        severity: "warn", summary: "MBQ Wedge", detail: msg, life: 4000,
                    });
                    console.warn(`[MBQ Wedge] ${msg}`);
                } else if (slotName) {
                    const w = this.widgets?.find(w => w.name === "parameter_name");
                    if (w) w.value = slotName;
                }
            }
            app.graph?.setDirtyCanvas(true, true);
        };
    },

    // Intercept api.queuePrompt once after registration.
    // Handles both numeric MBQWedge and string MBQWedge* nodes in a single wrapper.
    // Each wedge type expands one Queue click into N separate single-value jobs so
    // every PNG's prompt chunk carries the exact swept value.
    setup() {
        const _origQueue = api.queuePrompt.bind(api);
        api.queuePrompt = async function(number, data) {
            const prompt = data?.output ?? data?.prompt;
            if (!prompt) return _origQueue(number, data);

            // A wedge only counts as "active" if its output is actually wired to
            // a downstream parameter — mirrors the connection check in mbq_parser.py
            // so a stray/disconnected wedge sitting in the graph is ignored.
            const isWired = (id) => Object.values(prompt).some(node =>
                node?.inputs && Object.values(node.inputs).some(
                    v => Array.isArray(v) && String(v[0]) === id
                )
            );

            // ── Numeric wedge candidate ────────────────────────────────────────
            const numericId = Object.keys(prompt).find(
                id => prompt[id]?.class_type === "MBQWedge" && isWired(id)
            );
            let numericValues = null;
            if (numericId) {
                const inp   = prompt[numericId].inputs;
                const start = parseFloat(inp.start);
                const step  = parseFloat(inp.increment);
                const stop  = parseFloat(inp.stop);
                if (!isNaN(start) && !isNaN(step) && step > 0 && !isNaN(stop)) {
                    // Compute sweep values — mirrors Python Decimal logic at float precision
                    const values = [];
                    let v = start;
                    while (v <= stop + 1e-9) {
                        values.push(Math.round(v * 100) / 100);
                        v = Math.round((v + step) * 1e9) / 1e9;
                    }
                    if (values.length > 0) numericValues = values;
                }
            }

            // ── String wedge candidate (Sampler / Scheduler) ───────────────────
            const strWedgeId = Object.keys(prompt).find(
                id => STR_WEDGE_TYPES.includes(prompt[id]?.class_type) && isWired(id)
            );
            let strValues = null;
            if (strWedgeId) {
                const graphNode = app.graph?.nodes?.find(n => String(n.id) === String(strWedgeId));
                if (graphNode?._mbqStringValues?.length) strValues = graphNode._mbqStringValues;
            }

            const key = "output" in data ? "output" : "prompt";

            // ── Sanity check: only one wedge may drive a sweep at a time ───────
            // Multiple connected wedges (numeric + Scheduler, or Sampler + Scheduler,
            // etc.) is ambiguous — silently picking one produces confusing,
            // order-dependent results. Refuse to guess.
            const activeKinds = [];
            if (numericValues) activeKinds.push(prompt[numericId]?.class_type ?? "MBQWedge");
            if (strValues)     activeKinds.push(prompt[strWedgeId]?.class_type ?? "MBQWedge");
            if (activeKinds.length > 1) {
                const msg = `Multiple MBQ Wedge nodes are connected at once (${activeKinds.join(", ")}). `
                          + `Only one can drive a sweep — queuing a single normal job instead. `
                          + `Disconnect the extra wedge(s) to resume sweeping.`;
                app.extensionManager?.toast?.add?.({
                    severity: "warn", summary: "MBQ Wedge", detail: msg, life: 6000,
                });
                console.warn(`[MBQ Wedge] ${msg}`);

                // The numeric MBQWedge has OUTPUT_IS_LIST=True in Python, so even
                // submitting the prompt completely unmodified, ComfyUI's own server-side
                // execution will still expand start..stop into N separate renders —
                // independent of our JS. Clamp it to a single value so the fallback
                // submission can't silently multiply images behind the warning.
                if (numericId) {
                    const safePrompt = JSON.parse(JSON.stringify(prompt));
                    if (safePrompt[numericId]) {
                        safePrompt[numericId].inputs.stop = safePrompt[numericId].inputs.start;
                    }
                    return _origQueue(number, { ...data, [key]: safePrompt });
                }
                return _origQueue(number, data);
            }

            // Advances seeds per control_after_generate, then re-serializes the graph
            // so each subsequent job in the sweep carries the freshly advanced seed.
            const reserializePrompt = async () => {
                for (const node of app.graph?.nodes ?? []) {
                    for (const widget of node.widgets ?? []) {
                        if (typeof widget.afterQueued === "function") widget.afterQueued();
                    }
                }
                try {
                    const fresh = await app.graphToPrompt();
                    return fresh.output ?? fresh.prompt;
                } catch (_) {
                    return null;
                }
            };

            // Shared by both wedge types: submit one job per value, re-serializing the
            // graph between jobs (via reserializePrompt) so seeds advance correctly.
            // patchFn mutates the cloned prompt to set that job's swept value.
            const runSweep = async (values, patchFn) => {
                let lastResult;
                for (let i = 0; i < values.length; i++) {
                    const currentPrompt = i === 0
                        ? JSON.parse(JSON.stringify(prompt))
                        : (await reserializePrompt()) ?? JSON.parse(JSON.stringify(prompt));
                    patchFn(currentPrompt, values[i]);
                    lastResult = await _origQueue(number, { ...data, [key]: currentPrompt });
                }
                return lastResult;
            };

            if (numericValues) {
                return runSweep(numericValues, (p, val) => {
                    if (p[numericId]) {
                        p[numericId].inputs.start   = val;
                        p[numericId].inputs.stop    = val;
                        p[numericId].inputs.current = val;
                    }
                });
            }

            if (strValues) {
                return runSweep(strValues, (p, val) => {
                    if (p[strWedgeId]) {
                        p[strWedgeId].inputs.current = val;
                    }
                });
            }

            return _origQueue(number, data);
        };
    },
});
