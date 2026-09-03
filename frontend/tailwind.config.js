/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        saffron: {
          50: '#fff8f0',
          100: '#ffefdb',
          200: '#ffdbb3',
          300: '#ffc180',
          400: '#ffa74d',
          500: '#FF9933', // Official Saffron Primary
          600: '#e67e1a',
          700: '#cc6600',
          800: '#994d00',
          900: '#663300',
        },
        navy: {
          50: '#f0f4ff',
          100: '#e0e9ff',
          200: '#c7d7fe',
          300: '#a4bcfd',
          400: '#7c98fb',
          500: '#536df6',
          600: '#3447e8',
          700: '#2534ce',
          800: '#000080', // Official Navy Blue Accent
          900: '#000055',
          950: '#060a2b',
        },
        rail: {
          saffron: '#FF9933',
          navy: '#000080',
          dark: '#0a0f24',
          card: '#ffffff',
          border: '#e2e8f0',
          emergency: '#DC2626',
          urgent: '#F59E0B',
          normal: '#000080',
          civil: '#2563EB',
          electrical: '#D97706',
          signal: '#7C3AED',
          success: '#059669',
        }
      }
    },
  },
  plugins: [],
}
