"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const nav = [
  { href: "/", label: "总览", mark: "01" },
  { href: "/workflows", label: "工作流", mark: "02" },
  { href: "/runs", label: "运行证据", mark: "03" },
  { href: "/experiments", label: "正式实验", mark: "04" },
  { href: "/settings", label: "连接设置", mark: "05" },
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
            <small>AgentGym</small>
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
          <div className="tiny-label">安全边界</div>
          <p>GUI 只生成命令并读取证据；账户状态只能由确定性环境更新。</p>
          <span className="status-line">
            <i className="status-dot" /> rc2 · guarded
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
