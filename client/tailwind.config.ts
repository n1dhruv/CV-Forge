import type { Config } from 'tailwindcss'

export default {
  content: ['./src/app/**/*.{ts,tsx}', './src/components/**/*.{ts,tsx}', './src/screens/**/*.{ts,tsx}'],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      fontFamily: {
        display: ['Newsreader', 'Georgia', 'serif'],
        sans: ['"Instrument Sans"', 'Avenir Next', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
      colors: {
        canvas: 'var(--canvas)',
        surface: 'var(--surface)',
        raised: 'var(--raised)',
        elevated: 'var(--elevated)',
        ink: 'var(--ink)',
        muted: 'var(--muted)',
        subtle: 'var(--subtle)',
        line: 'var(--line)',
        'line-soft': 'var(--line-soft)',
        accent: 'var(--accent)',
        'accent-soft': 'var(--accent-soft)',
        'accent-hover': 'var(--accent-hover)',
        success: 'var(--success)',
        warning: 'var(--warning)',
        danger: 'var(--danger)',
      },
      boxShadow: {
        sm: 'var(--shadow-sm)',
        md: 'var(--shadow-md)',
        quiet: 'var(--shadow-lg)',
        elevated: 'var(--shadow-elevated)',
      },
      borderRadius: {
        sm: 'var(--radius-sm)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
        xl: 'var(--radius-xl)',
      },
      spacing: {
        section: 'var(--space-section)',
      },
      transitionDuration: {
        micro: 'var(--duration-micro)',
        fast: 'var(--duration-fast)',
        normal: 'var(--duration-normal)',
      },
      transitionTimingFunction: {
        'out-expo': 'var(--ease-out-expo)',
        'out-quart': 'var(--ease-out-quart)',
      },
    },
  },
  plugins: [],
} satisfies Config
