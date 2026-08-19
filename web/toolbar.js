import { app } from "../../scripts/app.js";


const openReferenceLibrary = () => {
    window.open(`${window.location.origin}/h3-references`, "_blank");
};


app.registerExtension({
    name: "H3ReferenceLibrary.Toolbar",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "H3TaggedReferencePrompt") {
            return;
        }

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = onNodeCreated?.apply(this, arguments);
            this.addWidget("button", "Open Reference Library", null, openReferenceLibrary);
            return result;
        };
    },
    actionBarButtons: [
        {
            icon: "icon-[lucide--library] size-4",
            tooltip: "Open H3 Reference Library",
            onClick: openReferenceLibrary,
        },
    ],
});
