"use strict";

module.exports = {
    extends: ["octane", "ember-template-lint-typed-templates:recommended"],
    rules: {
        "require-input-label": false,
        "no-invalid-interactive": false,
        "no-curly-component-invocation": false,
    },
    plugins: ["ember-template-lint-typed-templates"],
};
