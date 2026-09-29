import pluginVue from 'eslint-plugin-vue'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'
import skipFormatting from '@vue/eslint-config-prettier/skip-formatting'

export default defineConfigWithVueTs(
  { name: 'app/files', files: ['**/*.{ts,vue}'] },
  { name: 'app/ignores', ignores: ['dist/**', 'coverage/**', 'node_modules/**'] },
  pluginVue.configs['flat/recommended'],
  vueTsConfigs.recommended,
  skipFormatting,
  {
    rules: {
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      // Optional props are typed as `T | undefined` in TS; a runtime default
      // adds nothing and forces defaults for props that are genuinely absent.
      'vue/require-default-prop': 'off',
    },
  },
  {
    // Design-system primitives are intentionally single-word, matching the
    // component names they wrap (Button, Badge, Card).
    name: 'app/ui-primitives',
    files: ['src/shared/ui/**/*.vue'],
    rules: { 'vue/multi-word-component-names': 'off' },
  },
)
