import Link from "next/link";
import { AppShell, StatusPill } from "./components/AppShell";
import { demoRuns, phase12Status } from "./lib/data";

export default function Home() {
  return (
    <AppShell
      eyebrow="Research Control Center"
      title="让每次实验都有边界、有证据、可重放"
      description="编排 CrossMarketAgentGym 工作流，审阅冻结协议与运行证据。控制台不会直接修改账户，也不会把测试集带入调参。"
      action={
        <Link className="button primary" href="/workflows">
          创建工作流 <span aria-hidden="true">→</span>
        </Link>
      }
    >
      <section className="alert alert-warn" aria-label="阶段状态警告">
        <div className="alert-mark">!</div>
        <div>
          <strong>Phase 12 机器门禁完成，尚不是冻结结论</strong>
          <p>
            215 / 215 个运行已完成且无失败；独立复核仍缺失，因此
            Phase 12 未关闭、Phase 13 不可进入。
          </p>
        </div>
        <StatusPill tone="warn">{phase12Status.blocker}</StatusPill>
      </section>

      <section className="metric-grid" aria-label="项目指标">
        <article className="metric-card">
          <span>已完成运行</span>
          <strong>{phase12Status.completedRuns}</strong>
          <small>of {phase12Status.totalRuns} · 0 failed</small>
        </article>
        <article className="metric-card">
          <span>数据覆盖</span>
          <strong>{phase12Status.markets}</strong>
          <small>markets · {phase12Status.symbols} symbols</small>
        </article>
        <article className="metric-card">
          <span>冻结协议</span>
          <strong className="mono metric-text">{phase12Status.protocol}</strong>
          <small>{phase12Status.matrix}</small>
        </article>
        <article className="metric-card">
          <span>发布状态</span>
          <strong className="metric-text">v1.0.0-rc2</strong>
          <small>Phase 11 closed</small>
        </article>
      </section>

      <div className="dashboard-grid">
        <section className="panel span-2">
          <div className="panel-head">
            <div>
              <div className="tiny-label">Protocol pipeline</div>
              <h2>研究门禁</h2>
            </div>
            <StatusPill tone="good">会计误差 &lt; 1e-8</StatusPill>
          </div>
          <div className="gate-list">
            {[
              ["01", "数据清单冻结", "manifest + SHA-256", "pass"],
              ["02", "泄漏与会计测试", "test partition isolated", "pass"],
              ["03", "训练 / Agent / HPO", "统一 AgentRuntime", "pass"],
              ["04", "计算重放", "numerically_reproduced", "pass"],
              ["05", "独立复核", "review signature missing", "wait"],
            ].map(([number, label, note, state]) => (
              <div className="gate-row" key={number}>
                <span className="step-number">{number}</span>
                <div>
                  <strong>{label}</strong>
                  <small>{note}</small>
                </div>
                <span className={`gate-state ${state}`}>
                  {state === "pass" ? "通过" : "等待"}
                </span>
              </div>
            ))}
          </div>
        </section>

        <aside className="panel protocol-card">
          <div className="tiny-label">Deterministic guard</div>
          <h2>风险层在线</h2>
          <div className="radar-disc" aria-hidden="true">
            <span>RISK</span>
          </div>
          <ul className="check-list">
            <li>LLM 不可直接修改账户</li>
            <li>测试集不对 HPO 可见</li>
            <li>指令必须通过动作投影</li>
            <li>API Key 不进入浏览器</li>
          </ul>
        </aside>
      </div>

      <div className="dashboard-grid lower">
        <section className="panel span-2">
          <div className="panel-head">
            <div>
              <div className="tiny-label">Evidence ledger</div>
              <h2>最近运行</h2>
            </div>
            <Link className="text-link" href="/runs">
              查看全部 →
            </Link>
          </div>
          <div className="run-table" role="table" aria-label="最近运行">
            {demoRuns.map((run) => (
              <div className="run-row" role="row" key={run.id}>
                <div>
                  <strong className="mono">{run.id}</strong>
                  <small>{run.kind}</small>
                </div>
                <span>{run.protocol}</span>
                <StatusPill tone={run.status === "verified" ? "good" : "warn"}>
                  {run.status}
                </StatusPill>
              </div>
            ))}
          </div>
        </section>

        <section className="panel quick-panel">
          <div className="tiny-label">Quick actions</div>
          <h2>从证据开始</h2>
          <Link href="/workflows">生成安全训练命令 <span>→</span></Link>
          <Link href="/runs">导入 run manifest <span>→</span></Link>
          <Link href="/experiments">审阅 Phase 12 <span>→</span></Link>
          <Link href="/settings">连接只读服务 <span>→</span></Link>
        </section>
      </div>
    </AppShell>
  );
}
