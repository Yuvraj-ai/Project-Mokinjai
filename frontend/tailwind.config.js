/** @type {import('tailwindcss').Config} */

/*
  Semantic tokens map to CSS variables in src/index.css (light + .dark).
  The legacy cream/ink-numeric/accent scales were removed at the end of the
  port once grep confirmed zero usages. Only the semantic text-ink tiers
  (DEFAULT/muted/subtle) remain.
*/
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        // retired serif alias: font-display now renders the UI sans
        display: ['Inter', 'system-ui', 'sans-serif'],
        body: ['Inter', 'system-ui', 'sans-serif'],
        mono: ["'JetBrains Mono'", 'ui-monospace', 'monospace'],
      },
      colors: {
        canvas: 'var(--canvas)',
        surface: {
          DEFAULT: 'var(--surface)',
          muted: 'var(--surface-muted)',
          raised: 'var(--raised)',
        },
        line: {
          DEFAULT: 'var(--line)',
          strong: 'var(--line-strong)',
        },
        primary: {
          DEFAULT: 'var(--primary)',
          hover: 'var(--primary-hover)',
          fg: 'var(--primary-fg)',
        },
        ring: {
          DEFAULT: 'var(--ring)',
        },
        status: {
          success: {
            DEFAULT: 'var(--success)',
            soft: 'var(--success-soft)',
          },
          warning: {
            DEFAULT: 'var(--warning)',
            soft: 'var(--warning-soft)',
          },
          error: {
            DEFAULT: 'var(--danger)',
            soft: 'var(--danger-soft)',
          },
          info: {
            DEFAULT: 'var(--info)',
            soft: 'var(--info-soft)',
          },
        },
        chart: {
          1: 'var(--chart-1)',
          2: 'var(--chart-2)',
        },
        ink: {
          // new semantic text tiers
          DEFAULT: 'var(--text)',
          muted: 'var(--text-muted)',
          subtle: 'var(--text-subtle)',
        },
      },
      boxShadow: {
        menu: '0 4px 16px rgba(20, 20, 18, 0.08)',
        drawer: '0 12px 40px rgba(20, 20, 18, 0.16)',
      },
      accentColor: {
        primary: 'var(--primary)',
        ink: 'var(--text)',
      },
      animation: {
        'fade-in': 'fadeIn 0.4s cubic-bezier(0.22, 1, 0.36, 1) forwards',
        'fade-in-up': 'fadeInUp 0.5s cubic-bezier(0.22, 1, 0.36, 1) forwards',
        'slide-in-right': 'slideInRight 0.4s cubic-bezier(0.22, 1, 0.36, 1) forwards',
        'slide-in-left': 'slideInLeft 0.4s cubic-bezier(0.22, 1, 0.36, 1) forwards',
        'scale-in': 'scaleIn 0.3s cubic-bezier(0.22, 1, 0.36, 1) forwards',
      },
      keyframes: {
        fadeIn: {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        fadeInUp: {
          from: { opacity: '0', transform: 'translateY(20px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        slideInRight: {
          from: { opacity: '0', transform: 'translateX(12px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
        slideInLeft: {
          from: { opacity: '0', transform: 'translateX(-12px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
        scaleIn: {
          from: { opacity: '0', transform: 'scale(0.96)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
      },
    },
  },
  plugins: [],
}
