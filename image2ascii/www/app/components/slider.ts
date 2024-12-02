import Component from "@glimmer/component";

export interface SliderSignature {
    Args: {
        id: string;
        label: string;
        value: string;
    };
    Element: HTMLInputElement;
}

export default class SliderComponent extends Component<SliderSignature> {}
