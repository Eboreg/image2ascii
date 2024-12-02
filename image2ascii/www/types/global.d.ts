import "@glint/environment-ember-loose";
import "ember-source/types";
import { HelperLike } from "@glint/template";
import type htmlsafe from "./helpers/html-safe";
import type RenderModifiersRegistry from "@ember/render-modifiers/template-registry";
import type EmberTruthRegistry from "ember-truth-helpers/template-registry";
import type ApplicationController from "www/controllers/application";
import type OptionComponent from "www/components/option";
import type CheckboxComponent from "www/components/checkbox";
import type ResultBoxComponent from "www/components/result-box";
import type formatSliderValue from "www/helpers/format-slider-value";
import type toString from "www/helpers/to-string";
import type SliderComponent from "www/components/slider";

// Types for compiled templates
declare module "www/templates/*" {
    import { TemplateFactory } from "ember-cli-htmlbars";

    const tmpl: TemplateFactory;
    export default tmpl;
}

declare module "@glint/environment-ember-loose/registry" {
    export type PageTitle = abstract new <T>() => InstanceType<
        HelperLike<{
            Args: {
                Positional: [value: T];
            };
            Return: "";
        }>
    >;

    export default interface Registry extends RenderModifiersRegistry, EmberTruthRegistry {
        "format-slider-value": typeof formatSliderValue;
        "page-title": PageTitle;
        "html-safe": typeof htmlsafe;
        "to-string": typeof toString;
        Option: typeof OptionComponent;
        Checkbox: typeof CheckboxComponent;
        ResultBox: typeof ResultBoxComponent;
        Slider: typeof SliderComponent;
    }
}

declare module "@ember/controller" {
    interface Registry {
        application: ApplicationController;
    }
}

export interface Flag {
    value: string;
    text: string;
}

export interface Checkbox {
    id: string;
    label: string;
    text: string;
    checked: boolean;
    onChange: (value: boolean) => void;
}

export interface BackendResponse {
    checkboxes: {
        color: boolean;
        crop: boolean;
        invert: boolean;
        negative: boolean;
        "fill-all": boolean;
        "full-rgb": boolean;
    };
    sliders: {
        brightness: string;
        "color-balance": string;
        contrast: string;
    };
    version: string;
    output?: string;
    uuid?: string;
    flag?: string;
}
