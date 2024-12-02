"use strict";

module.exports = {
    overrides: [
        {
            files: "*.{js,ts}",
            options: {
                singleQuote: false,
                tabWidth: 4,
                printWidth: 120,
                trailingComma: "all",
            },
        },
        {
            files: "*.{hbs,handlebars}",
            options: {
                tabWidth: 2,
            },
        },
    ],
};
