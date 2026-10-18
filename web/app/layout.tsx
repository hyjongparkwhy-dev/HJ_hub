import type { Metadata, Viewport } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "HJ Briefing",
  description: "투자·부동산·기술 뉴스 아침 브리핑",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#F3F4F6" },
    { media: "(prefers-color-scheme: dark)", color: "#0E1013" },
  ],
};

// Pretendard is not on Google Fonts; its dynamic subset loads only the Korean glyphs a page uses.
const PRETENDARD =
  "https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css";

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ko">
      <head>
        <link rel="stylesheet" href={PRETENDARD} crossOrigin="anonymous" />
      </head>
      <body>
        <nav className="topbar" aria-label="메뉴">
          <Link href="/" className="brand">HJ Briefing</Link>
          <span>
            <Link href="/">브리핑</Link>
            <Link href="/search">검색</Link>
            <Link href="/projects">프로젝트</Link>
          </span>
        </nav>
        {children}
      </body>
    </html>
  );
}
