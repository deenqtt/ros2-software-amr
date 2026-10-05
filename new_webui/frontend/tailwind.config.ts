import type { Config } from 'tailwindcss'
import animate from 'tailwindcss-animate'
import plugin from 'tailwindcss/plugin'

/** `rgb(var(--x) / <alpha-value>)` keeps Tailwind opacity modifiers working. */
const c = (name: string) => `rgb(var(--${name}) / <alpha-value>)`

export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: c('primary'),
          active: c('primary-active'),
          disabled: c('primary-disabled'),
        },
        canvas: c('canvas'),
        surface: {
          DEFAULT: c('surface'),
          soft: c('surface-soft'),
          strong: c('surface-strong'),
        },
        ink: c('ink'),
        body: c('body'),
        muted: { DEFAULT: c('muted'), soft: c('muted-soft') },
        hairline: { DEFAULT: c('hairline'), soft: c('hairline-soft') },
        on: { primary: c('on-primary') },
        status: {
          idle: c('status-idle'),
          run: c('status-run'),
          act: c('status-act'),
          warn: c('status-warn'),
          fault: c('status-fault'),
          ok: c('status-ok'),
        },
      },
      borderColor: { DEFAULT: c('hairline') },
      borderRadius: {
        // Semantic, not a t-shirt scale — the name says what it is for, so a
        // control cannot quietly drift onto a card radius. See tokens.css for
        // why the pill was retired from rectangles.
        chip: 'var(--radius-chip)',
        control: 'var(--radius-control)',
        surface: 'var(--radius-surface)',
      },
      spacing: {
        // Base unit 4px, per DESIGN.md.
        xxs: '4px',
        xs: '8px',
        sm: '12px',
        base: '16px',
        md: '20px',
        lg: '24px',
        xl: '32px',
        xxl: '48px',
      },
      fontFamily: {
        // See docs/TYPOGRAPHY.md. Inter carries UI and numbers; JetBrains Mono
        // is reserved for identifiers (topic names, frame ids, URLs, logs).
        sans: ['Inter', '-apple-system', 'system-ui', 'Segoe UI', 'Roboto', 'sans-serif'],
        display: ['Inter', '-apple-system', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      fontSize: {
        // Console scale. Display tokens keep the source's negative tracking;
        // body and below stay at 0, exactly as the reference specifies.
        'display-sm': ['28px', { lineHeight: '1.11', letterSpacing: '-0.5px', fontWeight: '400' }],
        'title-lg': ['22px', { lineHeight: '1.18', letterSpacing: '-0.3px', fontWeight: '400' }],
        'title-md': ['18px', { lineHeight: '1.33', fontWeight: '600' }],
        'title-sm': ['15px', { lineHeight: '1.27', fontWeight: '600' }],
        'body-md': ['14px', { lineHeight: '1.5' }],
        'body-sm': ['13px', { lineHeight: '1.5' }],
        caption: ['12px', { lineHeight: '1.5' }],
        // 11px floor. The old UI went to 9px, unreadable standing at a robot.
        label: ['11px', { lineHeight: '1.45', letterSpacing: '0.06em', fontWeight: '600' }],
        'number-lg': ['22px', { lineHeight: '1.3', fontWeight: '500' }],
        'number-md': ['15px', { lineHeight: '1.4', fontWeight: '500' }],
        'number-sm': ['12px', { lineHeight: '1.4', fontWeight: '500' }],
      },
      height: {
        header: '64px', // top-nav height, straight from DESIGN.md
        control: '36px', // 44px marketing CTA, one step down for console
        'control-sm': '30px',
        nav: '38px',
      },
      width: {
        // Square icon buttons: same figures as the heights above. Without
        // these, size="icon" asked for a w-control that did not exist and
        // every icon button rendered as a sliver.
        control: '36px',
        'control-sm': '30px',
        sidebar: '232px',
        'sidebar-collapsed': '64px',
      },
      boxShadow: {
        // The source documents exactly one shadow tier. So do we.
        soft: '0 4px 12px rgb(0 0 0 / 0.04)',
      },
      transitionTimingFunction: {
        out: 'cubic-bezier(0.23, 1, 0.32, 1)',
      },
    },
  },
  plugins: [
    animate,
    // `touch:` — fingers, not a mouse. Controls grow to the 44px a fingertip
    // needs (Apple HIG, Material 48dp); a laptop with a mouse keeps the dense
    // console sizes. Keyed on the pointer, not the width: a tablet in landscape
    // is as wide as a laptop and still driven by touch.
    plugin(({ addVariant }) => addVariant('touch', '@media (pointer: coarse)')),
  ],
} satisfies Config
