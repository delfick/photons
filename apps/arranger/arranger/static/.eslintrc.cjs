module.exports = {
  root: true,
  globals: {
    NODE_ENV: true,
  },
  env: {
    browser: true,
  },
  rules: {
    "import/no-unresolved": "error",
    "node/no-missing-import": "off",
    "node/no-unsupported-features/es-syntax": [
      "error",
      { ignores: ["modules"] },
    ],
    "react/prop-types": "off",
    "react/display-name": "off",
    "@typescript-eslint/no-explicit-any": "off",
    "prefer-const": "off",
    "no-unused-vars": "off",
    "no-empty-function": "off",
    "@typescript-eslint/no-unused-vars": [
      "error",
      { varsIgnorePattern: "^_.*" },
    ],
  },
  overrides: [
    {
      files: ["webpack.config.ts"],
      rules: {
        "node/no-unpublished-require": "off",
        "node/no-unpublished-import": "off",
        "import/no-extraneous-dependencies": "off",
      },
    },
  ],
  settings: {
    "import/resolver": {
      typescript: {},
    },
    "import/parsers": {
      "@typescript-eslint/parser": [".ts", ".tsx"],
    },
    react: {
      version: "detect",
    },
  },
  parser: "@typescript-eslint/parser",
  plugins: [
    "@typescript-eslint",
    "import",
    "node",
    "react",
    "react-hooks",
    "import",
  ],
  extends: [
    "plugin:@typescript-eslint/recommended",
    "eslint:recommended",
    "plugin:import/recommended",
    "plugin:import/typescript",
    "plugin:import/errors",
    "plugin:import/warnings",
    "plugin:import/recommended",
    "plugin:node/recommended",
    "plugin:react/recommended",
    "plugin:react/jsx-runtime",
    "plugin:react-hooks/recommended",
    "prettier",
  ],
};
