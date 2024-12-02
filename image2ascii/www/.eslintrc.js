"use strict";

module.exports = {
    root: true,
    parser: "@typescript-eslint/parser",
    parserOptions: {
        ecmaVersion: "latest",
    },
    plugins: ["ember", "@typescript-eslint"],
    extends: ["eslint:recommended", "plugin:ember/recommended", "plugin:prettier/recommended"],
    env: {
        browser: true,
    },
    ignorePatterns: ["**/node_modules/", "**/.venv/", "tmp/", "lib/", "express/", "**/.mypy_cache/"],
    rules: {
        "require-input-label": "off",
        indent: ["warn", 4, { SwitchCase: 1 }],
        "max-len": ["warn", { code: 120 }],
        "ember/no-controller-access-in-routes": ["error", { allowControllerFor: true }],
        "ember/avoid-leaking-state-in-ember-objects": "off",
        "no-empty": "off",
    },
    overrides: [
        // d.ts files
        {
            files: ["**/*.d.ts"],
            extends: ["plugin:@typescript-eslint/eslint-recommended", "plugin:@typescript-eslint/recommended"],
            rules: {
                "max-len": "off",
            },
        },
        // ts files
        {
            files: ["**/*.ts"],
            extends: ["plugin:@typescript-eslint/eslint-recommended", "plugin:@typescript-eslint/recommended"],
            rules: {
                "@typescript-eslint/no-unused-vars": "warn",
                "@typescript-eslint/no-explicit-any": "off",
                "@typescript-eslint/ban-ts-comment": "off",
            },
        },
        // node files
        {
            files: [
                "./.eslintrc.js",
                "./.prettierrc.js",
                "./.stylelintrc.js",
                "./.template-lintrc.js",
                "./ember-cli-build.js",
                "./testem.js",
                "./blueprints/*/index.js",
                "./config/**/*.js",
                "./lib/*/index.js",
                "./server/**/*.js",
            ],
            env: {
                browser: false,
                node: true,
            },
            extends: ["plugin:n/recommended"],
        },
        {
            // test files
            files: ["tests/**/*-test.{js,ts}"],
            extends: ["plugin:qunit/recommended"],
        },
    ],
};
