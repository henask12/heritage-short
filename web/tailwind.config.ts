/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0B0A0C",
        ash: "#1A1618",
        mist: "#E8E0D6",
        bone: "#F4EEE6",
        crimson: "#C8102E",
        ember: "#8B0E1E",
        gold: "#C9A227",
      },
      fontFamily: {
        display: ["var(--font-display)", "Georgia", "serif"],
        body: ["var(--font-body)", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      backgroundImage: {
        "hero-veil":
          "linear-gradient(180deg, rgba(11,10,12,0.25) 0%, rgba(11,10,12,0.55) 45%, rgba(11,10,12,0.92) 100%)",
        "section-glow":
          "radial-gradient(ellipse 80% 60% at 20% 0%, rgba(200,16,46,0.22), transparent 55%)",
      },
      keyframes: {
        rise: {
          "0%": { opacity: "0", transform: "translateY(18px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        drift: {
          "0%, 100%": { transform: "scale(1.05) translate3d(0,0,0)" },
          "50%": { transform: "scale(1.1) translate3d(-1.5%, 1%, 0)" },
        },
        pulseLine: {
          "0%, 100%": { transform: "scaleX(0.55)", opacity: "0.55" },
          "50%": { transform: "scaleX(1)", opacity: "1" },
        },
      },
      animation: {
        rise: "rise 0.9s ease-out both",
        "rise-late": "rise 1.1s ease-out 0.15s both",
        "rise-later": "rise 1.2s ease-out 0.3s both",
        drift: "drift 22s ease-in-out infinite",
        "pulse-line": "pulseLine 3.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
