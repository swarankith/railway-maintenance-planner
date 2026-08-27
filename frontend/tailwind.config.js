/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        rail: {
          dark: '#0B132B',
          navy: '#1C2541',
          blue: '#3A506B',
          accent: '#00B4D8',
          track: '#48CAE4',
          electric: '#F72585',
          signal: '#7209B7',
          civil: '#3A86FF',
          emergency: '#E63946',
          success: '#10B981',
          warning: '#F59E0B'
        }
      }
    },
  },
  plugins: [],
}
