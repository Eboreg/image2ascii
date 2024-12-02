import { action } from "@ember/object";
import Component from "@glimmer/component";
import type { Checkbox } from "global";

export interface CheckboxSignature {
    Args: {
        data: Checkbox;
    };
    Element: HTMLInputElement;
}

export default class CheckboxComponent extends Component<CheckboxSignature> {
    @action onChange() {
        this.args.data.checked = !this.args.data.checked;
        this.args.data.onChange(this.args.data.checked);
    }
}
