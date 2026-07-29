"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const nav = [
  { href: "/", label: "首页", mark: "⌂" },
  { href: "/workflows", label: "创建策略", mark: "策" },
  { href: "/runs", label: "回测记录", mark: "绩" },
  { href: "/experiments", label: "策略参考", mark: "参" },
  { href: "/settings", label: "设置", mark: "设" },
];

export function AppShell({
  children,
  eyebrow,
  title,
  description,
  action,
}: {
  children: ReactNode;
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div className="app-frame">
      <aside className="sidebar">
        <Link className="brand" href="/" aria-label="CrossMarketAgentGym 首页">
          <span className="brand-mark" aria-hidden="true">
            CM
          </span>
          <span>
            <strong>CrossMarket</strong>
            <small>智能策略实验室</small>
          </span>
        </Link>

        <nav className="side-nav" aria-label="主导航">
          {nav.map((item) => {
            const active =
              pathname === item.href ||
              (item.href !== "/" && pathname.startsWith(item.href));
            return (
              <Link
                href={item.href}
                key={item.href}
                className={active ? "active" : undefined}
                aria-current={active ? "page" : undefined}
              >
                <span>{item.mark}</span>
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="sidebar-foot">
          <div className="tiny-label">安心使用</div>
          <p>仓位、现金和交易成本限制会在每次模拟交易前自动检查。</p>
          <span className="status-line">
            <i className="status-dot" /> 风险保护已开启
          </span>
        </div>
      </aside>

      <main className="main">
        <header className="page-head">
          <div>
            <div className="eyebrow">{eyebrow}</div>
            <h1>{title}</h1>
            <p>{description}</p>
          </div>
          {action && <div className="page-action">{action}</div>}
        </header>
        {children}
      </main>
    </div>
  );
}

export function StatusPill({
  tone,
  children,
}: {
  tone: "good" | "warn" | "bad" | "neutral";
  children: ReactNode;
}) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}
