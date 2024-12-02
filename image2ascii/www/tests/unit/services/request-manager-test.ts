import { module, test } from "qunit";
import { setupTest } from "www/tests/helpers";

module("Unit | Service | request-manager", function (hooks) {
    setupTest(hooks);

    // TODO: Replace this with your real tests.
    test("it exists", function (assert) {
        const service = this.owner.lookup("service:request-manager");
        assert.ok(service);
    });
});
