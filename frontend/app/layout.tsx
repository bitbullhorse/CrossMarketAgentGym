import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(
    "https://crossmarket-agent-gym.chenzhenjiang05.chatgpt.site",
  ),
  title: {
    default: "CrossMarketAgentGym · 智能策略实验室",
    template: "%s · CrossMarketAgentGym",
  },
  description:
    "无需编程即可创建、训练和回测跨市场智能交易策略。",
  openGraph: {
    title: "CrossMarketAgentGym 智能策略实验室",
    description: "通过图形化向导创建、训练和回测跨市场智能策略",
    images: [{ url: "/og.png", width: 1536, height: 1024 }],
  },
  twitter: {
    card: "summary_large_image",
    title: "CrossMarketAgentGym 智能策略实验室",
    description: "无需编程，创建并回测你的跨市场智能策略",
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
