"use strict";

const EmberApp = require("ember-cli/lib/broccoli/ember-app");

module.exports = function (defaults) {
    const env = EmberApp.env() || "development";

    const app = new EmberApp(defaults, {
        "ember-cli-babel": { enableTypeScriptTransform: true },
        babel: { sourceMaps: "inline" },
        sourcemaps: {
            enabled: env == "development",
        },
    });

    return app.toTree();
};
