import { module, test } from "qunit";
import { setupTest } from "www/tests/helpers";

module("Unit | Route | application", function (hooks) {
    setupTest(hooks);

    test("it exists", function (assert) {
        const route = this.owner.lookup("route:application");
        assert.ok(route);
    });
});
