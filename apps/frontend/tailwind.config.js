/** @type {import('tailwindcss').Config} */

// Brand ramp — anchored on the two brand blues (#00A3FF cyan, #010978 deep blue).
// `indigo`/`violet` are remapped to this so existing accent utilities pick up the brand.
const brand = {
  50:  '#E6F4FF',
  100: '#CCE9FF',
  200: '#99D3FF',
  300: '#66BDFF',
  400: '#33B3FF',
  500: '#00A3FF',
  600: '#0086D6',
  700: '#015FB0',
  800: '#013A8C',
  900: '#010978',
  950: '#01063F',
}

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter Variable"', 'Inter', '"SF Pro Display"', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', '"Open Sans"', '"Helvetica Neue"', 'sans-serif'],
        mono: ['"SF Mono"', '"Fira Code"', '"Cascadia Code"', 'Consolas', 'monospace'],
      },
      colors: {
        brand,
        indigo: brand,
        violet: brand,
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
}
