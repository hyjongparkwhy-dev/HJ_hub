import type { Metadata, Viewport } from "next";
import { IBM_Plex_Sans_KR, Noto_Serif_KR } from "next/font/google";
import Link from "next/link";
import "./globals.css";

// Korean glyphs are not a selectable subset, so the files load on demand instead of being preloaded.
const display = Noto_Serif_KR({ weight: ["600", "800"], preload: false, variable: "--font-display", display: "swap" });
const body = IBM_Plex_Sans_KR({ weight: ["400", "600"], preload: false, variable: "--font-body", display: "swap" });

export const metadata: Metadata = {
  title: "HJ 아침 신문",
  description: "투자·부동산·기술 뉴스 아침 브리핑",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#F3EFE6" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ko" className={`${display.variable} ${body.variable}`}>
      <body>
        <header className="masthead">
          <Link href="/" className="masthead-name">HJ 아침 신문</Link>
          <nav aria-label="메뉴">
            <Link href="/">브리핑</Link>
            <Link href="/search">검색</Link>
          </nav>
        </header>
        {children}
      </body>
    </html>
  );
}
