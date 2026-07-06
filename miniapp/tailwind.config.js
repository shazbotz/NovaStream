/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        accent: {
          DEFAULT: "#7c5cff",
          dark: "#5b3fd6",
        },
      },
    },
  },
  plugins: [],
};
