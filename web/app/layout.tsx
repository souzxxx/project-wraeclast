import type { Metadata } from "next";
import { Cinzel, EB_Garamond, Spline_Sans_Mono } from "next/font/google";
import "./globals.css";
import Nav from "./nav";

// Arcane-grimoire type system: engraved display caps, an old-style serif body, a ledger mono.
const display = Cinzel({
  subsets: ["latin"],
  weight: ["500", "600", "700", "800"],
  variable: "--font-cinzel",
  display: "swap",
});
const body = EB_Garamond({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  style: ["normal", "italic"],
  variable: "--font-garamond",
  display: "swap",
});
const mono = Spline_Sans_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono-spline",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Project Wraeclast",
  description: "Auto-updating Path of Exile 2 advisor — economy, farms, craft, chat.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${mono.variable}`}>
      <body>
        <Nav />
        {children}
      </body>
    </html>
  );
}
