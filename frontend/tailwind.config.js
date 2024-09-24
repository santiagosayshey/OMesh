// tailwind.config.js
module.exports = {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        dark: {
          100: "#1E293B",
          200: "#334155",
          300: "#475569",
        },
      },
    },
  },
  darkMode: "class",
  plugins: [],
};
