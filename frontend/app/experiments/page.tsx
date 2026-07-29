import Link from "next/link";
import { AppShell, StatusPill } from "../components/AppShell";
import { agentRows, baselineRows, hpoRows, transferRows } from "../lib/data";

function BarTable({
  rows,
  valueKey,
  suffix = "",
  max,
}: {
  rows: { name: string; return?: number; score?: number }[];
  valueKey: "return" | "score";
  suffix?: string;
  max: number;
}) {
  return (
    <div className="bar-table">
      {rows.map((row) => {
        const value = Number(row[valueKey] ?? 0);
        return (
          <div className="bar-row" key={row.name}>
            <span>{row.name}</span>
            <div className="bar-track" aria-hidden="true">
              <i style={{ width: `${Math.max(1.5, (value / max) * 100)}%` }} />
            </div>
            <strong>
              {value.toFixed(valueKey === "score" ? 3 : 2)}
              {suffix}
            </strong>
          </div>
        );
      })}
    </div>
  );
}

export default function ExperimentsPage() {
  return (
    <AppShell
      eyebrow="Strategy guide"
      title="选择策略方法的参考"
      description="下面是内置历史样本上的示例表现，用于帮助理解不同算法的特点。它不是收益承诺，也不能替代你在自己数据上的回测。"
      action={
        <Link className="button primary" href="/workflows">
          创建我的策略
        </Link>
      }
    >
      <section className="alert alert-warn consumer-alert">
        <div className="alert-mark">i</div>
        <div>
          <strong>先理解差异，再自己验证</strong>
          <p>
            这些方法在当前样本中的差异没有达到统计显著水平。
            历史表现不代表未来收益，请结合回撤、成本和换手率一起判断。
          </p>
        </div>
        <StatusPill tone="warn">仅供参考</StatusPill>
      </section>

      <section className="method-intro-grid">
        <article className="panel method-intro">
          <span>PPO</span>
          <h2>稳定、容易开始</h2>
          <p>适合首次训练和多数跨市场配置，是默认推荐选择。</p>
          <Link href="/workflows?mode=train">使用 PPO 创建 →</Link>
        </article>
        <article className="panel method-intro">
          <span>SAC</span>
          <h2>探索更充分</h2>
          <p>适合连续仓位决策，通常需要更多训练时间。</p>
          <Link href="/workflows?mode=train">尝试 SAC →</Link>
        </article>
        <article className="panel method-intro">
          <span>TD3</span>
          <h2>适合高级特征</h2>
          <p>支持张量观察和自定义特征提取，适合有经验的用户。</p>
          <Link href="/workflows?mode=train">尝试 TD3 →</Link>
        </article>
      </section>

      <div className="experiment-grid">
        <article className="panel experiment-card span-2">
          <div className="panel-head">
            <div>
              <div className="tiny-label">历史样本表现</div>
              <h2>常见策略的区间回报</h2>
            </div>
            <span className="period">2025-01-02 — 2025-09-30</span>
          </div>
          <BarTable
            rows={baselineRows}
            valueKey="return"
            suffix="%"
            max={15}
          />
          <p className="chart-note">
            等权策略在这个样本中的回报较高，SAC 的风险调整后表现较好。
            单个样本不能说明某种方法长期更优。
          </p>
        </article>

        <article className="panel experiment-card">
          <div className="tiny-label">跨市场适应</div>
          <h2>迁移到不同市场</h2>
          <BarTable
            rows={transferRows}
            valueKey="return"
            suffix="%"
            max={12}
          />
          <p className="chart-note">
            联合训练在当前样本中更稳定；迁移到单一市场时表现差异较大。
          </p>
        </article>

        <article className="panel experiment-card">
          <div className="tiny-label">真实摩擦</div>
          <h2>成本和市场机制的影响</h2>
          <div className="delta-list">
            {[
              ["忽略交易费用", "+2.61 个百分点", "up"],
              ["忽略滑点", "+1.29 个百分点", "up"],
              ["降低风险限制", "+1.14 个百分点", "warn"],
              ["取消换手限制", "−0.50 个百分点", "down"],
              ["忽略汇率变化", "−3.06 个百分点", "down"],
              ["强制同步交易日", "−5.79 个百分点", "down"],
            ].map(([name, value, tone]) => (
              <div key={name}>
                <span>{name}</span>
                <strong className={tone}>{value}</strong>
              </div>
            ))}
          </div>
          <p className="chart-note">
            忽略成本可能让回测看起来更好，但会降低结果的现实参考价值。
          </p>
        </article>

        <article className="panel experiment-card">
          <div className="tiny-label">AI 顾问组合</div>
          <h2>不同顾问配置</h2>
          <BarTable
            rows={agentRows}
            valueKey="return"
            suffix="%"
            max={6}
          />
          <p className="chart-note">
            风险委员会可能主动降低仓位。回报降低并不一定代表建议失效，
            还需要同时观察回撤和风险暴露。
          </p>
        </article>

        <article className="panel experiment-card">
          <div className="panel-head">
            <div>
              <div className="tiny-label">参数优化</div>
              <h2>相同预算下的优化评分</h2>
            </div>
          </div>
          <BarTable rows={hpoRows} valueKey="score" max={1.9} />
          <p className="chart-note">
            没有一种搜索方法在所有策略上都最好。首次使用可从粒子群或随机搜索开始。
          </p>
        </article>
      </div>
    </AppShell>
  );
}
