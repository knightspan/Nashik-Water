import type { Config } from 'tailwindcss';

/** Colours are CSS variables (see src/index.css) so light/dark mode swap in one place. */
const v = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        paper: v('bg'),
        ink: v('fg'),
        surface: v('surface'),
        line: v('line'),
        muted: v('muted'),
        subtle: v('subtle'),
        water: v('accent'),
        echo: { 1: v('echo-1'), 2: v('echo-2'), 3: v('echo-3'), 4: v('echo-4') },
        // Verdict colours are fixed by the project spec; always paired with a text label.
        status: {
          green: '#2e7d32',
          amber: '#f9a825',
          red: '#c62828',
          grey: '#9e9e9e',
        },
      },
      fontFamily: {
        display: ['"Clash Display"', 'Mukta', 'system-ui', 'sans-serif'],
        sans: ['Satoshi', 'Mukta', 'system-ui', 'sans-serif'],
        serif: ['"Instrument Serif"', 'Georgia', 'serif'],
      },
      letterSpacing: { tightest: '-0.05em' },
      lineHeight: { crush: '0.9' },
      transitionTimingFunction: { reveal: 'cubic-bezier(0.77, 0, 0.175, 1)' },
      height: { header: '80px' },
    },
  },
  plugins: [],
} satisfies Config;
