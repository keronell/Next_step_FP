/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        cream: 'var(--color-cream)',
        navy: 'var(--color-navy)',
        'navy-light': 'var(--color-navy-light)',
        gold: 'var(--color-gold)',
        'gold-light': 'var(--color-gold-light)',
        accent: 'var(--accent)',
        surface: 'var(--surface)',
        ink: 'var(--ink)',
        'ink-soft': 'var(--ink-soft)',
      },
      fontFamily: {
        display: ['"Playfair Display"', 'Georgia', 'serif'],
        body: ['Inter', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        eyebrow: ['0.75rem',  { lineHeight: '1',    letterSpacing: '0.18em' }],
        small:   ['0.875rem', { lineHeight: '1.5' }],
        body:    ['1rem',     { lineHeight: '1.65' }],
        h3:      ['1.25rem',  { lineHeight: '1.35', letterSpacing: '-0.005em' }],
        h2:      ['1.875rem', { lineHeight: '1.2',  letterSpacing: '-0.01em' }],
        h1:      ['clamp(2.25rem, 4vw + 1rem, 3.75rem)', { lineHeight: '1.05', letterSpacing: '-0.02em' }],
        display: ['clamp(2.5rem, 5.5vw + 1rem, 6rem)',   { lineHeight: '1.02', letterSpacing: '-0.025em' }],
      },
      borderRadius: {
        card: 'var(--radius-card)',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px) rotate(0deg)' },
          '33%': { transform: 'translateY(-20px) rotate(5deg)' },
          '66%': { transform: 'translateY(10px) rotate(-3deg)' },
        },
        'count-up': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'spin-slow': {
          '0%': { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(360deg)' },
        },
        'aurora-1': {
          '0%, 100%': { transform: 'translate(0%, 0%) scale(1)' },
          '25%': { transform: 'translate(18%, -16%) scale(1.18)' },
          '50%': { transform: 'translate(-14%, 14%) scale(0.85)' },
          '75%': { transform: 'translate(10%, -8%) scale(1.08)' },
        },
        'aurora-2': {
          '0%, 100%': { transform: 'translate(0%, 0%) scale(1)' },
          '25%': { transform: 'translate(-16%, 16%) scale(1.1)' },
          '50%': { transform: 'translate(16%, -16%) scale(0.9)' },
          '75%': { transform: 'translate(-8%, 8%) scale(1.16)' },
        },
        'aurora-pan': {
          '0%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
          '100%': { backgroundPosition: '0% 50%' },
        },
        shimmer: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
        'shimmer-slide': {
          '0%': { backgroundPosition: '0% 0%' },
          '100%': { backgroundPosition: '-200% 0%' },
        },
        glow: {
          '0%, 100%': { opacity: '0.4' },
          '50%': { opacity: '0.8' },
        },
      },
      animation: {
        float: 'float 8s ease-in-out infinite',
        'float-delayed': 'float 10s ease-in-out 2s infinite',
        'float-slow': 'float 12s ease-in-out 4s infinite',
        'spin-slow': 'spin-slow 2s linear infinite',
        'aurora-1': 'aurora-1 22s ease-in-out infinite',
        'aurora-2': 'aurora-2 26s ease-in-out infinite',
        'aurora-pan': 'aurora-pan 18s linear infinite',
        shimmer: 'shimmer 2.5s ease-in-out infinite',
        'shimmer-slide': 'shimmer-slide 3s linear infinite',
        glow: 'glow 4s ease-in-out infinite',
      },
      transitionDuration: {
        fast: '180ms',
        base: '240ms',
        slow: '360ms',
        2500: '2500ms',
        400: '400ms',
      },
      transitionTimingFunction: {
        standard: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)',
        elastic: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      },
    },
  },
  plugins: [],
}
