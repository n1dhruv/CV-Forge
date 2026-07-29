import type { Config } from 'tailwindcss'
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: { extend: {
    fontFamily: { display: ['Newsreader', 'Georgia', 'serif'], sans: ['"Instrument Sans"', 'Avenir Next', 'sans-serif'], mono: ['"IBM Plex Mono"', 'monospace'] },
    colors: { canvas: 'var(--canvas)', surface: 'var(--surface)', raised: 'var(--raised)', ink: 'var(--ink)', muted: 'var(--muted)', line: 'var(--line)', accent: 'var(--accent)', 'accent-soft': 'var(--accent-soft)', success: 'var(--success)', warning: 'var(--warning)', danger: 'var(--danger)' },
    boxShadow: { quiet: '0 12px 40px color-mix(in oklch, var(--ink) 7%, transparent)' },
    borderRadius: { xl: '1rem', '2xl': '1.35rem' }
  }}, plugins: []
} satisfies Config
