import { TrackedObject } from "tracked-built-ins";
import Controller from "@ember/controller";
import config from "../config/environment";
import { tracked } from "@glimmer/tracking";
import { action } from "@ember/object";
import type { BackendResponse, Checkbox, Flag } from "global";
import { service } from "@ember/service";
import type RequestManagerService from "www/services/request";
import type { ApplicationModel } from "www/routes/application";

export default class ApplicationController extends Controller<ApplicationModel> {
    declare model: ApplicationModel;

    pointingUrl = config.rootURL + "images/pointing.png";
    queryParams = ["uuid"];

    @service declare request: RequestManagerService;
    @tracked uuid?: string;
    @tracked isLoading: boolean = true;

    get checkboxes(): Checkbox[] {
        const boxes = [
            this.#getCheckbox("color", "Colour", "Outputs in glorious ANSI colour."),
            this.#getCheckbox("crop", "Crop", "Crops empty areas at all edges."),
            this.#getCheckbox("invert", "Invert", "Fills characters that would have been empty, and vice versa."),
            this.#getCheckbox("negative", "Negative", "Inverts the colours of the image before processing."),
            this.#getCheckbox(
                "fill-all",
                "Fill all",
                "If checked, all sections of the image (except for any transparent ones) will be filled.",
            ),
            this.#getCheckbox(
                "full-rgb",
                "Full RGB",
                "Whether to make use of all 16,777,216 RGB colours, instead of the 16 predefined ANSI colours.",
            ),
        ];

        return boxes;
    }

    get isNoFlagSelected(): boolean {
        return this.model.flag == undefined;
    }

    get pageTitle() {
        return `Image2ASCII v${this.model.version}`;
    }

    constructor(...args: any) {
        super(...args);

        document.addEventListener("paste", (event) => {
            // Handle pasted images
            event.preventDefault();
            event.stopPropagation();

            const file = event.clipboardData?.files.item(0);

            if (file) this.uploadFile(file);
        });
    }

    @action isFlagSelected(flag: Flag) {
        return flag.value == this.model.flag;
    }

    @action onFileSelect(event: Event) {
        event.preventDefault();
        event.stopPropagation();

        if (event.target instanceof HTMLInputElement && event.target.files) {
            const file = event.target.files.item(0);
            if (file) this.uploadFile(file);
        }
    }

    @action onFlagSelect(event: Event) {
        if (event.target instanceof HTMLSelectElement) {
            const value = event.target.value;

            if (value) {
                this.model.checkboxes.color = true;
                this.model.checkboxes["fill-all"] = true;
                this.model.checkboxes["full-rgb"] = true;
                this.model.checkboxes.invert = false;
                this.model.checkboxes.negative = false;
                this.model.checkboxes.crop = false;
                this.model.sliders.brightness = "1";
                this.model.sliders.contrast = "1";
                this.model.sliders["color-balance"] = "1";
                this.model.flag = value;

                this.#post("post-flag", { flag: value });
            }
        }
    }

    @action onResetClick() {
        this.model.checkboxes.color = true;
        this.model.checkboxes["fill-all"] = false;
        this.model.checkboxes["full-rgb"] = true;
        this.model.checkboxes.invert = false;
        this.model.checkboxes.negative = false;
        this.model.checkboxes.crop = true;
        this.model.sliders.brightness = "1";
        this.model.sliders.contrast = "1";
        this.model.sliders["color-balance"] = "1";

        this.#post("post", {});
    }

    @action onUrlDrop(url: string) {
        this.#post("post-url", { url: url });
    }

    @action onUpdateClick() {
        this.#post("post", {});
    }

    @action async uploadFile(file: File) {
        this.#post("post-file", {
            file: {
                size: file.size,
                type: file.type,
                name: file.name,
                contents: await this.#fileToBase64(file),
            },
        });
    }

    #fileToBase64(file: File): Promise<string> {
        return new Promise((resolve: (value: string) => void, reject) => {
            const reader = new FileReader();

            reader.readAsDataURL(file);
            reader.onload = () => resolve((reader.result as string).replace(/^data:.*?\/.*?;base64,/, ""));
            reader.onerror = reject;
        });
    }

    #getCheckbox(id: keyof BackendResponse["checkboxes"], label: string, text: string): Checkbox {
        return new TrackedObject({
            id: id,
            label: label,
            text: text,
            checked: this.model.checkboxes[id] as boolean,
            onChange: (value: boolean) => {
                this.model.checkboxes[id] = value;
            },
        });
    }

    #getPostData() {
        return {
            checkboxes: this.model.checkboxes,
            sliders: this.model.sliders,
            uuid: this.model.uuid,
        };
    }

    async #post(endpoint: string, data: any) {
        this.isLoading = true;

        const response = await this.request.request({
            method: "POST",
            url: `http://localhost:8000/${endpoint}`,
            body: JSON.stringify({ ...this.#getPostData(), ...data }),
            headers: new Headers({ "Content-Type": "application/json" }),
        });
        const content = response.content as BackendResponse;

        if (content.uuid == this.uuid) this.isLoading = false;

        this.model.checkboxes = content.checkboxes;
        this.model.output = content.output;
        this.model.uuid = content.uuid;
        this.uuid = content.uuid;
    }
}
