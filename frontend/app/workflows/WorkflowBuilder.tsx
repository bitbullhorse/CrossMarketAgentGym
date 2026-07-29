"use client";

import { useMemo, useState } from "react";
import { StatusPill } from "../components/AppShell";

const workflows = [
  { id: "data", label: "数据验证", note: "Manifest / schema / hashes" },
  { id: "env", label: "环境检查", note: "Gymnasium + SB3 + accounting" },
  { id: "train", label: "训练", note: "PPO / SAC / TD3" },
  { id: "agents", label: "Agent 委员会", note: "统一 AgentRuntime" },
  { id: "hpo", label: "超参数优化", note: "Searcher ≠ scheduler" },
  { id: "reproduce", label: "计算重放", note: "execute + compare" },
  { id: "report", label: "报告生成", note: "Evidence only" },
];

const searchers = [
  "random",
  "grid",
  "tpe",
  "cma_es",
  "nsga_ii",
  "pso",
  "genetic",
  "differential_evolution",
  "simulated_annealing",
];

export function WorkflowBuilder() {
  const [workflow, setWorkflow] = useState("train");
  const [algorithm, setAlgorithm] = useState("ppo");
  const [partition, setPartition] = useState("train");
  const [seed, setSeed] = useState(42);
  const [runId, setRunId] = useState("gui-ppo-quickstart");
  const [searcher, setSearcher] = useState("random");
  const [scheduler, setScheduler] = useState("none");
  const [agentCount, setAgentCount] = useState(3);
  const [research, setResearch] = useState(true);
  const [risk, setRisk] = useState(true);
  const [strategy, setStrategy] = useState(true);
  const [testAcknowledged, setTestAcknowledged] = useState(false);
  const [copied, setCopied] = useState(false);

  const command = useMemo(() => {
    const config = "configs/env/sample_cross_market.yaml";
    if (workflow === "data") return `cmag data validate --config ${config}`;
    if (workflow === "env") return `cmag env check --config ${config}`;
    if (workflow === "report") return `cmag report --run-id ${runId}`;
    if (workflow === "reproduce")
      return `cmag reproduce --run-id ${runId} --execute --compare`;
    if (workflow === "hpo") {
      const schedulerFlag =
        scheduler === "none" ? "" : ` --scheduler ${scheduler}`;
      return `cmag hpo --config configs/hpo/${searcher}.yaml --searcher ${searcher}${schedulerFlag} --seed ${seed}`;
    }
    if (workflow === "agents") {
      const layers = [
        research && "research",
        risk && "risk",
        strategy && "hierarchical_strategy",
      ]
        .filter(Boolean)
        .join(",");
      return `cmag agents run --config configs/agents/sample_committee.yaml --layers ${layers || "none"} --count ${agentCount} --seed ${seed}`;
    }
    return `cmag train --config configs/trainer/${algorithm}_quickstart.yaml --run-id ${runId} --partition ${partition} --seed ${seed}`;
  }, [
    workflow,
    algorithm,
    partition,
    seed,
    runId,
    searcher,
    scheduler,
    agentCount,
    research,
    risk,
    strategy,
  ]);

  const blocked = partition === "test" && !testAcknowledged;

  async function copyCommand() {
    if (blocked) return;
    await navigator.clipboard.writeText(command);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="workflow-layout">
      <section className="workflow-rail panel" aria-label="工作流类型">
        <div className="tiny-label">Select workflow</div>
        <div className="workflow-tabs" role="tablist">
          {workflows.map((item, index) => (
            <button
              type="button"
              role="tab"
              aria-selected={workflow === item.id}
              className={workflow === item.id ? "selected" : undefined}
              onClick={() => {
                setWorkflow(item.id);
                setCopied(false);
              }}
              key={item.id}
            >
              <span>{String(index + 1).padStart(2, "0")}</span>
              <strong>{item.label}</strong>
              <small>{item.note}</small>
            </button>
          ))}
        </div>
      </section>

      <section className="panel builder-panel">
        <div className="panel-head">
          <div>
            <div className="tiny-label">Resolved configuration</div>
            <h2>{workflows.find((item) => item.id === workflow)?.label}</h2>
          </div>
          <StatusPill tone="neutral">CPU first</StatusPill>
        </div>

        <div className="form-grid">
          {(workflow === "train" || workflow === "hpo") && (
            <label className="field">
              <span>算法</span>
              <select
                value={algorithm}
                onChange={(event) => setAlgorithm(event.target.value)}
              >
                <option value="ppo">PPO</option>
                <option value="sac">SAC</option>
                <option value="td3">TD3</option>
              </select>
              <small>SB3 quickstart 默认使用 flat OHLCV 布局。</small>
            </label>
          )}

          {workflow === "train" && (
            <label className="field">
              <span>数据分区</span>
              <select
                value={partition}
                onChange={(event) => {
                  setPartition(event.target.value);
                  setTestAcknowledged(false);
                }}
              >
                <option value="train">train</option>
                <option value="validation">validation</option>
                <option value="test">test · locked</option>
              </select>
              <small>测试分区仅用于冻结协议的一次最终评估。</small>
            </label>
          )}

          {workflow === "hpo" && (
            <>
              <label className="field">
                <span>搜索算法</span>
                <select
                  value={searcher}
                  onChange={(event) => setSearcher(event.target.value)}
                >
                  {searchers.map((name) => (
                    <option value={name} key={name}>
                      {name}
                    </option>
                  ))}
                </select>
                <small>候选参数生成器；不得读取 test 指标。</small>
              </label>
              <label className="field">
                <span>资源调度器</span>
                <select
                  value={scheduler}
                  onChange={(event) => setScheduler(event.target.value)}
                >
                  <option value="none">none</option>
                  <option value="asha">ASHA</option>
                  <option value="hyperband">HyperBand</option>
                  <option value="pbt">Population Based Training</option>
                </select>
                <small>调度器独立于搜索器，不改变目标函数定义。</small>
              </label>
            </>
          )}

          {workflow === "agents" && (
            <>
              <div className="field full-field">
                <span>Agent 层</span>
                <div className="toggle-grid">
                  {[
                    ["Research orchestration", research, setResearch],
                    ["Risk management", risk, setRisk],
                    ["Hierarchical strategy", strategy, setStrategy],
                  ].map(([name, value, setter]) => (
                    <label className="toggle-row" key={String(name)}>
                      <input
                        type="checkbox"
                        checked={Boolean(value)}
                        onChange={(event) =>
                          (setter as (value: boolean) => void)(
                            event.target.checked,
                          )
                        }
                      />
                      <span>{String(name)}</span>
                    </label>
                  ))}
                </div>
                <small>三层可独立开关，但始终共享统一 AgentRuntime。</small>
              </div>
              <label className="field">
                <span>参与 Agent 数量</span>
                <input
                  type="number"
                  min={1}
                  max={12}
                  value={agentCount}
                  onChange={(event) => setAgentCount(Number(event.target.value))}
                />
              </label>
              <div className="field">
                <span>在线模型</span>
                <div className="readonly-value">deepseek-v4-pro</div>
                <small>API Key 只从后端环境变量读取。</small>
              </div>
            </>
          )}

          {!["data", "env"].includes(workflow) && workflow !== "hpo" && (
            <label className="field full-field">
              <span>Run ID</span>
              <input
                value={runId}
                onChange={(event) =>
                  setRunId(event.target.value.replace(/\s+/g, "-"))
                }
                spellCheck={false}
              />
              <small>原运行永不覆盖；重放会创建独立目录。</small>
            </label>
          )}

          {!["data", "env", "report", "reproduce"].includes(workflow) && (
            <label className="field">
              <span>随机种子</span>
              <input
                type="number"
                value={seed}
                onChange={(event) => setSeed(Number(event.target.value))}
              />
            </label>
          )}
        </div>

        {partition === "test" && workflow === "train" && (
          <div className="alert alert-danger compact-alert">
            <div className="alert-mark">×</div>
            <div>
              <strong>锁定测试集不是开发分区</strong>
              <p>
                只有协议已经冻结、验证集选择完成且仅执行一次最终评估时才能继续。
              </p>
              <label className="ack-row">
                <input
                  type="checkbox"
                  checked={testAcknowledged}
                  onChange={(event) =>
                    setTestAcknowledged(event.target.checked)
                  }
                />
                我确认此次运行属于冻结协议的最终测试评估
              </label>
            </div>
          </div>
        )}

        <div className="command-block">
          <div className="command-head">
            <span>CLI PREVIEW</span>
            <span>只读生成 · 可复制审计</span>
          </div>
          <code>{command}</code>
          <button
            type="button"
            className="button primary"
            disabled={blocked}
            onClick={copyCommand}
          >
            {copied ? "已复制" : blocked ? "需要确认测试门禁" : "复制命令"}
          </button>
        </div>
      </section>

      <aside className="panel safety-panel">
        <div className="tiny-label">Execution contract</div>
        <h2>执行契约</h2>
        <div className="contract-item">
          <span>01</span>
          <div>
            <strong>配置先解析</strong>
            <p>CLI 保存 resolved config、数据 Manifest 与运行指纹。</p>
          </div>
        </div>
        <div className="contract-item">
          <span>02</span>
          <div>
            <strong>风险层不可绕过</strong>
            <p>Agent 只提出 directive，动作必须经过确定性投影。</p>
          </div>
        </div>
        <div className="contract-item">
          <span>03</span>
          <div>
            <strong>测试集隔离</strong>
            <p>测试集不对 HPO 可见；冻结 Benchmark 和重放证据不可覆盖。</p>
          </div>
        </div>
        <div className="contract-item">
          <span>04</span>
          <div>
            <strong>人工执行</strong>
            <p>请在受控终端审阅命令后执行；GUI 不拥有写权限。</p>
          </div>
        </div>
      </aside>
    </div>
  );
}
