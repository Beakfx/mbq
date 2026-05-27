import { app } from "/scripts/app.js";

function updateIterations(node) {
    if (node._mbqUpdating) return;
    node._mbqUpdating = true;
    try {
        const get = name => parseFloat(node.widgets?.find(w => w.name === name)?.value) || 0;
        const start = get("start");
        const step  = get("step_size");
        const stop  = get("stop");
        const count = step > 0 ? Math.max(0, Math.floor((stop - start) / step) + 1) : 0;
        const lbl   = node.widgets?.find(w => w.name === "_iterations");
        if (lbl) lbl.value = `${count} iteration${count !== 1 ? "s" : ""}`;
    } finally {
        node._mbqUpdating = false;
    }
}

// Only changes display precision — never touches w.value to avoid callback loops.
// Python already rounds INT output correctly via int(round(x)).
function updateWidgetMode(node) {
    const isInt = (node.outputs?.[0]?.links?.length ?? 0) > 0;
    for (const name of ["start", "step_size", "stop"]) {
        const w = node.widgets?.find(w => w.name === name);
        if (!w) continue;
        w.options = w.options ?? {};
        w.options.precision = isInt ? 0 : 2;
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

            for (const name of ["start", "step_size", "stop"]) {
                const w = this.widgets?.find(w => w.name === name);
                if (w) {
                    const orig = w.callback;
                    const node = this;
                    w.callback = function(...args) {
                        orig?.apply(this, args);
                        updateIterations(node);
                    };
                }
            }
            updateWidgetMode(this);
            updateIterations(this);
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
            updateWidgetMode(this);
            updateIterations(this);
            app.graph?.setDirtyCanvas(true, true);
        };
    },


});
