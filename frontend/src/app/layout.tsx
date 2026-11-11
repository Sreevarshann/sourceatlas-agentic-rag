import type { Metadata } from "next";
import { Fraunces, Inter, JetBrains_Mono } from "next/font/google";
import Script from "next/script";
import { Providers } from "@/components/Providers";
import { themeInitScript } from "@/components/theme";
import "./globals.css";

const display = Fraunces({ variable: "--font-display", subsets: ["latin"], axes: ["opsz", "SOFT"] });
const body = Inter({ variable: "--font-body", subsets: ["latin"] });
const code = JetBrains_Mono({ variable: "--font-code", subsets: ["latin"] });

export const metadata: Metadata = { title: { default: "SourceAtlas", template: "%s · SourceAtlas" }, description: "Explore knowledge. Trace every answer." };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="light" suppressHydrationWarning className={`${display.variable} ${body.variable} ${code.variable}`}>
      <body className="min-h-dvh">
        <Script id="theme" strategy="beforeInteractive">{themeInitScript}</Script>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
