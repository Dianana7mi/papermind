import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "PaperMind · Research Workspace",
  description: "Evidence-grounded scientific experiment analysis",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
