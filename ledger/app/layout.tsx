import type { Metadata } from "next";
import { Newsreader, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

// Newsreader carries an optical-size axis, which is the one thing that lets a single
// family behave like a broadsheet's display-plus-text pairing. next/font self-hosts at
// build time, so there is no runtime CDN request and no layout shift.
const newsreader = Newsreader({
  variable: "--font-newsreader",
  subsets: ["latin"],
  axes: ["opsz"],
  display: "swap",
});

// The mono owns every numeral. This page is read DOWN columns of numbers, and
// proportional figures make a column of numbers ragged and measurably slower to scan.
const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "The Storm Ledger - volatility regimes across eleven markets",
  description:
    "A hidden Markov model sorts eleven markets into three volatility states, out of sample. Volatility orders 11 of 11. Return orders 2. The states rank risk, not return.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${newsreader.variable} ${plexMono.variable} antialiased`}>
      <body>{children}</body>
    </html>
  );
}
