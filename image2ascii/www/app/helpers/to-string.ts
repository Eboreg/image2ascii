import { helper } from "@ember/component/helper";

function toString(args: [value: any]): string {
    return String(args[0]);
}

export default helper(toString);
