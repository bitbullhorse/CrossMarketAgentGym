import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://crossmarketagentgym.example"),
  title: {
    default: "CrossMarketAgentGym · Research Control Center",
    template: "%s · CrossMarketAgentGym",
  },
  description:
    "可审计的跨市场智能体研究控制台：编排训练、复现运行并审阅冻结实验。",
  openGraph: {
    title: "CrossMarketAgentGym",
    description: "Auditable Research Control Center",
    images: [{ url: "/og.png", width: 1536, height: 1024 }],
  },
  twitter: {
    card: "summary_large_image",
    title: "CrossMarketAgentGym",
    description: "Auditable Research Control Center",
    images: ["/og.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
