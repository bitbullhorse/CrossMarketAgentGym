import { AppShell, StatusPill } from "../components/AppShell";
import {
  agentRows,
  baselineRows,
  hpoRows,
  phase12Status,
  transferRows,
} from "../lib/data";

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
      eyebrow="Frozen protocol · provisional results"
      title="Phase 12 正式实验"
      description="展示 protocol-v4 / matrix-v6 的机器执行结果。所有比较均为描述性结果；独立复核签字前不得作为最终论文结论。"
      action={<StatusPill tone="warn">review required</StatusPill>}
    >
      <section className="experiment-banner">
        <div>
          <span className="tiny-label">Machine gate</span>
          <strong>215 / 215</strong>
          <small>runs completed</small>
        </div>
        <div>
          <span className="tiny-label">Statistical gate</span>
          <strong>0 / 200</strong>
          <small>Holm-significant comparisons</small>
        </div>
        <div>
          <span className="tiny-label">Independent review</span>
          <strong>缺失</strong>
          <small>{phase12Status.blocker}</small>
        </div>
      </section>

      <section className="alert alert-warn">
        <div className="alert-mark">!</div>
        <div>
          <strong>阅读口径</strong>
          <p>
            200 个配对检验经 Holm 校正后均不显著，最小调整后 p 值为 1.0。
            B、E、F 有配对检验；C、D 仅作描述。下列“较高”不代表统计胜出。
          </p>
        </div>
      </section>

      <div className="experiment-grid">
        <article className="panel experiment-card span-2">
          <div className="panel-head">
            <div>
              <div className="tiny-label">Task B · Baselines</div>
              <h2>锁定测试区间回报</h2>
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
            Equal weight 描述性回报 14.97%；SAC 描述性 Sharpe 1.802。
            结果未年化，且不存在 Holm 校正后的显著优胜者。
          </p>
        </article>

        <article className="panel experiment-card">
          <div className="tiny-label">Task A · Accounting</div>
          <h2>无泄漏与会计一致性</h2>
          <div className="big-check">10 / 10</div>
          <p className="chart-note">测试用例通过；最大绝对会计误差 0.0。</p>
          <div className="mini-stats">
            <span>
              <strong>0</strong> leakage
            </span>
            <span>
              <strong>0</strong> mutation
            </span>
          </div>
        </article>

        <article className="panel experiment-card">
          <div className="tiny-label">Task C · Transfer</div>
          <h2>跨市场迁移</h2>
          <BarTable
            rows={transferRows}
            valueKey="return"
            suffix="%"
            max={12}
          />
          <p className="chart-note">仅作描述性对比；未执行配对显著性检验。</p>
        </article>

        <article className="panel experiment-card">
          <div className="tiny-label">Task D · Market mechanics</div>
          <h2>机制消融 · Δ return</h2>
          <div className="delta-list">
            {[
              ["No transaction cost", "+2.61 pp", "up"],
              ["No slippage", "+1.29 pp", "up"],
              ["Minimum risk layer", "+1.14 pp", "warn"],
              ["No turnover cap", "−0.50 pp", "down"],
              ["No FX", "−3.06 pp", "down"],
              ["Synchronous calendar", "−5.79 pp", "down"],
            ].map(([name, value, tone]) => (
              <div key={name}>
                <span>{name}</span>
                <strong className={tone}>{value}</strong>
              </div>
            ))}
          </div>
          <p className="chart-note">
            “Minimum risk layer”同时提高换手、成本与回撤，不能只看回报。
          </p>
        </article>

        <article className="panel experiment-card">
          <div className="tiny-label">Task E · Agent ablation</div>
          <h2>三层 Agent 消融</h2>
          <BarTable
            rows={agentRows}
            valueKey="return"
            suffix="%"
            max={6}
          />
          <p className="chart-note">
            完整委员会被确定性风险层投影为全现金；这说明安全约束生效，不表示
            LLM 组件无效。委员会平均 11,316 tokens / 87.3 秒。
          </p>
        </article>

        <article className="panel experiment-card span-2">
          <div className="panel-head">
            <div>
              <div className="tiny-label">Task F · HPO</div>
              <h2>等预算优化器评分</h2>
            </div>
            <StatusPill tone="neutral">24 trials · 3 folds · 1 test</StatusPill>
          </div>
          <BarTable rows={hpoRows} valueKey="score" max={1.9} />
          <p className="chart-note">
            Random 的描述性 locked-test score 为 1.879。ASHA 仅作为资源调度器；
            Grid 与 Simulated Annealing 已实现但不在冻结的 Phase 12 协议中。
          </p>
        </article>
      </div>

      <section className="provenance panel">
        <div>
          <div className="tiny-label">Provenance contract</div>
          <h2>所有数字必须回到运行源</h2>
        </div>
        <div className="provenance-flow">
          <span>run ID</span>
          <i>→</i>
          <span>source file</span>
          <i>→</i>
          <span>benchmark revision</span>
          <i>→</i>
          <span>paper version</span>
        </div>
        <p>
          独立复核完成前，本页仅作为审阅界面；不得以截图替代冻结结果文件或审计签名。
        </p>
      </section>
    </AppShell>
  );
}
