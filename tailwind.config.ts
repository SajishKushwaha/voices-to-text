import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./hooks/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        chat: {
          ink: "#17202a",
          muted: "#697687",
          surface: "#f3f5f8",
          panel: "#ffffff",
          green: "#128c7e",
          bubble: "#dcf8c6",
          slate: "#263238"
        }
      },
      boxShadow: {
        soft: "0 18px 60px rgba(23, 32, 42, 0.12)"
      }
    }
  },
  plugins: []
};

export default config;
