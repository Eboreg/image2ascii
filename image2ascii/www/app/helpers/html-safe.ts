import { helper } from "@ember/component/helper";
import { htmlSafe, type SafeString } from "@ember/template";

function markSafe(args: [text: string]): SafeString {
    return htmlSafe(args[0]);
}

export default helper(markSafe);
