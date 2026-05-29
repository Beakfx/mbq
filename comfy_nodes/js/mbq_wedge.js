import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

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

function updateWidgetMode(node, isInt) {
    node._mbqIsInt = !!isInt;
    for (const name of ["start", "stop", "increment"]) {
        const w = node.widgets?.find(w => w.name === name);
        if (!w || !w.options) continue;
        if (isInt) {
            // Save original precision on first INT connection, then force 0 decimals.
            if (w._mbqOrigPrecision === undefined) w._mbqOrigPrecision = w.options.precision;
            w.options.precision = 0;
            if (typeof w.value === "number") w.value = Math.round(w.value);
        } else {
            // Restore saved precision when switching back to FLOAT mode.
            if (w._mbqOrigPrecision !== undefined) {
                w.options.precision = w._mbqOrigPrecision;
                delete w._mbqOrigPrecision;
            }
        }
    }
}

app.registerExtension({
    name: "MBQ.Wedge",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "MBQWedge") return;
        console.log("[MBQ Wedge] JS extension loaded");

        nodeType.prototype.onNodeCreated = function() {
            const lbl = this.addWidget("text", "_iterations", "—", () => {}, { serialize: false });
            lbl.draw = function(ctx, node, widget_width, y, H) {
                ctx.save();
                ctx.font = "italic 13px Arial";
                ctx.fillStyle = "#ddd";
                ctx.textBaseline = "middle";
                ctx.fillText(`will produce → ${this.value}`, 6, y + H / 2);
                ctx.restore();
            };
            lbl.mouse = () => false;

            const cur = this.addWidget("text", "_current", "—", () => {}, { serialize: false });
            cur.draw = function(ctx, node, widget_width, y, H) {
                ctx.save();
                ctx.font = "italic 13px Arial";
                ctx.fillStyle = "#aaa";
                ctx.textBaseline = "middle";
                ctx.fillText(`current → ${this.value}`, 6, y + H / 2);
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
    },

    // Intercept api.queuePrompt once after registration.
    // When an MBQWedge node is present, expand the single multi-value submission
    // into N separate single-value jobs — same pattern ComfyUI uses for per-image
    // seed randomization. Each job gets start=stop=V and current=V patched in,
    // so every PNG's prompt chunk carries the exact swept value.
    setup() {
        const _origQueue = api.queuePrompt.bind(api);
        api.queuePrompt = async function(number, data) {
            const prompt = data?.output ?? data?.prompt;
            if (!prompt) return _origQueue(number, data);

            const wedgeId = Object.keys(prompt).find(
                id => prompt[id]?.class_type === "MBQWedge"
            );
            if (!wedgeId) return _origQueue(number, data);

            const inp   = prompt[wedgeId].inputs;
            const start = parseFloat(inp.start);
            const step  = parseFloat(inp.increment);
            const stop  = parseFloat(inp.stop);
            if (isNaN(start) || isNaN(step) || step <= 0 || isNaN(stop)) {
                return _origQueue(number, data);
            }

            // Compute sweep values — mirrors Python Decimal logic at float precision
            const values = [];
            let v = start;
            while (v <= stop + 1e-9) {
                values.push(Math.round(v * 100) / 100);
                v = Math.round((v + step) * 1e9) / 1e9;
            }
            if (values.length === 0) return _origQueue(number, data);

            const patchWedge = (p, val) => {
                if (p[wedgeId]) {
                    p[wedgeId].inputs.start     = val;
                    p[wedgeId].inputs.stop      = val;
                    p[wedgeId].inputs.increment = 1.0;
                    p[wedgeId].inputs.current   = val;
                }
            };

            const key = "output" in data ? "output" : "prompt";
            let lastResult;
            for (let i = 0; i < values.length; i++) {
                let currentPrompt;

                if (i === 0) {
                    currentPrompt = JSON.parse(JSON.stringify(prompt));
                } else {
                    // Fire afterQueued on every graph widget so seeds advance per their
                    // control_after_generate setting (randomize/increment/decrement/fixed),
                    // then re-serialize the graph to capture the updated seed values.
                    for (const node of app.graph?.nodes ?? []) {
                        for (const widget of node.widgets ?? []) {
                            if (typeof widget.afterQueued === "function") widget.afterQueued();
                        }
                    }
                    try {
                        const fresh = await app.graphToPrompt();
                        currentPrompt = fresh.output ?? fresh.prompt;
                    } catch (_) {}
                    if (!currentPrompt) currentPrompt = JSON.parse(JSON.stringify(prompt));
                }

                patchWedge(currentPrompt, values[i]);
                lastResult = await _origQueue(number, { ...data, [key]: currentPrompt });
            }
            return lastResult;
        };
    },
});
