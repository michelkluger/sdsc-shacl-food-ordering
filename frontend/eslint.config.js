import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist', 'node_modules'] },
  js.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked,
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: { 'react-hooks': reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      '@typescript-eslint/consistent-type-imports': 'error',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    },
  },
  {
    files: ['**/*.test.{ts,tsx}', 'src/test-setup.ts'],
    rules: { '@typescript-eslint/no-unsafe-assignment': 'off' },
  },
  {
    // JSON Forms declares `handleChange` on ControlProps with a method signature, so
    // destructuring it trips `unbound-method`. It is an ordinary function prop that never
    // references `this`; the rule is a false positive here and is scoped off accordingly
    // rather than being disabled for the whole project.
    files: ['src/renderers/**/*.tsx'],
    rules: { '@typescript-eslint/unbound-method': 'off' },
  },
)
