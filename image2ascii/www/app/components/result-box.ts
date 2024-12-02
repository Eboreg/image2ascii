import { action } from "@ember/object";
import Component from "@glimmer/component";
import { tracked } from "@glimmer/tracking";

export interface ResultBoxSignature {
    Args: {
        output?: string;
        "is-loading": boolean;
        "on-file-drop": (file: File) => void;
        "on-url-drop": (url: string) => void;
    };
    Element: HTMLDivElement;
}

export default class ResultBoxComponent extends Component<ResultBoxSignature> {
    @tracked isDraggingOver: boolean = false;

    get showDragOverlay() {
        return this.isDraggingOver && !this.args["is-loading"];
    }

    get showDragInfo() {
        return !this.isDraggingOver && !this.args.output && !this.args["is-loading"];
    }

    constructor(...args: ConstructorParameters<typeof Component<ResultBoxSignature>>) {
        super(...args);

        document.body.addEventListener("dragover", (event) => {
            event.preventDefault();
            event.stopPropagation();
            this.isDraggingOver = this.#isOverResultBox(event) && this.#hasData(event);
        });

        document.body.addEventListener("drop", (event) => {
            // Catching this so browser navigation will not be triggered.
            event.preventDefault();
            event.stopPropagation();
            this.isDraggingOver = false;
        });
    }

    @action onDragEnter(event: DragEvent) {
        event.preventDefault();
        event.stopPropagation();
        if (this.#isOverResultBox(event) && this.#hasData(event)) {
            this.isDraggingOver = true;
        }
    }

    @action onDragLeave(event: DragEvent) {
        event.preventDefault();
        if (this.#isOverResultBox(event)) {
            event.stopPropagation();
            this.isDraggingOver = false;
        }
    }

    @action onDrop(event: DragEvent) {
        event.preventDefault();
        event.stopPropagation();
        this.isDraggingOver = false;

        const file = this.#getFile(event);

        if (file) {
            this.args["on-file-drop"](file);
        } else if (event.dataTransfer) {
            const url = event.dataTransfer.getData("text");
            if (url) this.args["on-url-drop"](url);
        }
    }

    #getFile(event: DragEvent): File | undefined {
        if (event.dataTransfer) {
            if (event.dataTransfer.items.length > 0 && event.dataTransfer.items[0]?.kind == "file") {
                const file = event.dataTransfer.items[0].getAsFile();
                if (file) return file;
            }
            return event.dataTransfer.files.item(0) || undefined;
        }
        return;
    }

    #hasData(event: DragEvent): boolean {
        return (
            !!event.dataTransfer?.files.length ||
            !!event.dataTransfer?.items.length ||
            !!event.dataTransfer?.getData("text")
        );
    }

    #isOverResultBox(event: DragEvent): boolean {
        // No result for closest() = drag is outside result-box.
        return event.target instanceof HTMLElement && !!event.target.closest("#result-box");
    }
}
