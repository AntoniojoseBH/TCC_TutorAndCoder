module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg:      "#0f1117",
        surface: "#1a1f2e",
        panel:   "#1e2535",
        border:  "#2d3748",
        accent:  "#3b82f6",
        "accent-hover": "#2563eb",
        muted:   "#64748b",
        soft:    "#94a3b8",
        text:    "#e2e8f0",
        danger:  "#ef4444",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
    },
  },
  plugins: [],
};
