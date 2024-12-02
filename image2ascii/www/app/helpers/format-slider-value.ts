import { helper } from "@ember/component/helper";

function formatSliderValue(args: [value: any]): string {
    return parseFloat(args[0]).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

export default helper(formatSliderValue);
