import Component from "@glimmer/component";

export interface OptionSignature {
    Args: {
        selected?: boolean;
        value: string;
    };
    Blocks: {
        default: [];
    };
    Element: HTMLOptionElement;
}

export default class OptionComponent extends Component<OptionSignature> {}
