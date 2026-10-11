const hooks = require("eslint-plugin-react-hooks");
const react = require("eslint-plugin-react");
const globals = require("globals");

module.exports = [{
  files: ["src/**/*.{js,jsx}"],
  languageOptions: {
    ecmaVersion: "latest",
    sourceType: "module",
    parserOptions: { ecmaFeatures: { jsx: true } },
    globals: { ...globals.browser, process: "readonly", require: "readonly", module: "readonly", jest: "readonly" },
  },
  plugins: { "react-hooks": hooks, react },
  rules: {
    "react-hooks/rules-of-hooks": "error",
    "react-hooks/exhaustive-deps": "error",
    "no-undef": "error",
    "react/jsx-no-undef": "error",
  },
}];