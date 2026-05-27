import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "MBQ.Wedge",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "MBQWedge") return;

        const onConnectOutput = nodeType.prototype.onConnectOutput;
        nodeType.prototype.onConnectOutput = function(slot, type, input, target_node, target_slot) {
            const result = onConnectOutput?.apply(this, arguments);
            const slotName = target_node?.inputs?.[target_slot]?.name;
            if (slotName) {
                const w = this.widgets?.find(w => w.name === "parameter_name");
                if (w) w.value = slotName;
            }
            return result;
        };
    },
});
