import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";

// Non-type-checked recommended rules only -- type-checked linting would just duplicate what the
// build job's `tsc --noEmit` already covers, for real added CI time. Kept minimal to match the
// same "tractable baseline, not maximal" approach as the backend's ruff/mypy config.
export default tseslint.config(
  { ignores: ["dist"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    plugins: { "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
    },
  },
);
