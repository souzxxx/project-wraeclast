import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Project Wraeclast",
  description: "Auto-updating Path of Exile 2 advisor — economy, farms, build, chat.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
