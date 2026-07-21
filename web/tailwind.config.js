/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        chunam: '#EFE7D8',
        kaapi: '#2B1D14',
        oxide: {
          DEFAULT: '#9A3324',
          dark: '#7A2818',
          light: '#B54732',
        },
        verdigris: {
          DEFAULT: '#4B6B58',
          dark: '#3A5445',
          light: '#628778',
        },
        turmeric: '#C68A2E',
        sandstone: '#C7B79C',
        sandstone2: '#DDD0B8',
        paper: '#F7F2E7',
      },
      fontFamily: {
        display: ['"Fraunces"', 'serif'],
        body: ['"Work Sans"', 'sans-serif'],
        mono: ['"Space Mono"', 'monospace'],
      },
      backgroundImage: {
        grain: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.035'/%3E%3C/svg%3E\")",
      },
    },
  },
  plugins: [],
};
