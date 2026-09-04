import type { Metadata, Viewport } from "next";
import type * as React from "react";

import { AppShell } from "@/components/app-shell";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "RecoveryIQ Command Center", template: "%s · RecoveryIQ" },
  description: "Bounded, auditable revenue recovery operations",
  icons: {
    icon: "/icon.jpg",
  },
};

export const viewport: Viewport = {
  colorScheme: "light dark",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f4f7fb" },
    { media: "(prefers-color-scheme: dark)", color: "#080d13" },
  ],
};

const themeScript = `(() => { try { const saved = localStorage.getItem("recoveriq-theme"); const theme = saved === "light" || saved === "dark" ? saved : window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"; document.documentElement.classList.toggle("dark", theme === "dark"); document.documentElement.dataset.theme = theme; } catch (_) {} })();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: themeScript }} /></head>
      <body className="min-h-screen antialiased"><AppShell>{children}</AppShell></body>
    </html>
  );
}
