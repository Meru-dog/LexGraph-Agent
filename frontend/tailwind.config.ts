import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: "#2D4FD6",
        navy: "#1E3A5F",
        accent: "#4F46E5",
        "text-primary": "#111827",
        "text-secondary": "#374151",
        "text-muted": "#6B7280",
        border: "#E5E7EB",
        "border-light": "#F3F4F6",
        "bg-page": "#F5F6F8",
        "bg-card": "#FFFFFF",
        "bg-subtle": "#F9FAFB",
        "indigo-light": "#EEF2FF",
        "indigo-border": "#C7D2FA",
      },
      fontFamily: {
        serif: ["var(--font-dm-serif)", "Georgia", "serif"],
        sans: ["var(--font-ibm-plex-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-ibm-plex-mono)", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
