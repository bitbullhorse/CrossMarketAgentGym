"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { StatusPill } from "../components/AppShell";
import {
  cancelJob,
  getCapabilities,
  getConfigContent,
  getJob,
  getJobLog,
  listConfigs,
  readServiceBaseUrl,
  ServiceApiError,
  submitJob,
  validateConfig,
  type Capabilities,
  type ConfigCatalogEntry,
  type ConfigKind,
  type JobRecord,
  type JobRequest,
} from "../lib/api";

type Activity = "train" | "backtest" | "tune" | "agent";
type RiskProfile = "conservative" | "balanced" | "growth";
type Algorithm = "PPO" | "SAC" | "TD3";
type AgentPreset = "full_stack" | "team" | "research" | "offline";

const terminalStatuses = new Set(["completed", "failed", "cancelled"]);

const activities: {
  id: Activity;
  label: string;
  note: string;
  mark: string;
}[] = [
  {
    id: "train",
    label: "训练新策略",
    note: "选择算法与风险偏好",
    mark: "01",
  },
  {
    id: "backtest",
    label: "回测已有策略",
    note: "用历史行情检验表现",
    mark: "02",
  },
  {
    id: "tune",
    label: "自动优化参数",
    note: "寻找更合适的参数组合",
    mark: "03",
  },
  {
    id: "agent",
    label: "使用 AI 顾问",
    note: "研究、风控与市场状态分析",
    mark: "04",
  },
];

const riskProfiles: Record<
  RiskProfile,
  {
    label: string;
    note: string;
    maxAssetWeight: number;
    cashFloor: number;
    maxTurnover: number;
    maxDrawdown: number;
  }
> = {
  conservative: {
    label: "稳健",
    note: "更分散，保留较多现金",
    maxAssetWeight: 15,
    cashFloor: 30,
    maxTurnover: 20,
    maxDrawdown: 15,
  },
  balanced: {
    label: "均衡",
    note: "兼顾收益空间与风险",
    maxAssetWeight: 30,
    cashFloor: 10,
    maxTurnover: 35,
    maxDrawdown: 25,
  },
  growth: {
    label: "进取",
    note: "仓位更集中，波动可能更大",
    maxAssetWeight: 40,
    cashFloor: 5,
    maxTurnover: 50,
    maxDrawdown: 40,
  },
};

const searcherLabels: Record<string, string> = {
  random: "随机搜索",
  grid: "网格搜索",
  tpe: "TPE 贝叶斯优化",
  cma_es: "CMA-ES",
  nsga_ii: "NSGA-II 多目标优化",
  pso: "粒子群优化",
  genetic: "遗传算法",
  differential_evolution: "差分进化",
  simulated_annealing: "模拟退火",
};

const schedulerLabels: Record<string, string> = {
  fifo: "全部运行完成",
  median: "中位数提前停止",
  asha: "ASHA 节省资源",
  hyperband: "HyperBand 分配预算",
  pbt: "PBT 动态调整",
};

const activityConfigKind: Partial<Record<Activity, ConfigKind>> = {
  train: "train",
  tune: "tune",
  agent: "agent",
};

function friendlyError(error: unknown): string {
  if (error instanceof ServiceApiError && error.status === 0) {
    return "未连接到本地策略服务。请前往“设置”检查连接。";
  }
  return error instanceof Error ? error.message : "操作失败，请稍后重试。";
}

function portableName(value: string, fallback: string): string {
  const normalized = value
    .trim()
    .replace(/\s+/g, "-")
    .replace(/[^A-Za-z0-9_.-]/g, "")
    .slice(0, 80);
  return normalized || fallback;
}

function yamlScalar(value: string | number | boolean): string {
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") return Number.isInteger(value) ? `${value}` : `${value}`;
  return /^[A-Za-z0-9_./-]+$/.test(value) ? value : JSON.stringify(value);
}

function setTopLevel(
  yaml: string,
  key: string,
  value: string | number | boolean,
): string {
  const line = `${key}: ${yamlScalar(value)}`;
  const pattern = new RegExp(`^${key}:.*$`, "m");
  return pattern.test(yaml) ? yaml.replace(pattern, line) : `${line}\n${yaml}`;
}

function setSectionValue(
  yaml: string,
  section: string,
  key: string,
  value: string | number | boolean,
): string {
  const lines = yaml.split(/\r?\n/);
  const sectionIndex = lines.findIndex((line) => line.trim() === `${section}:`);
  if (sectionIndex < 0) return `${yaml.trimEnd()}\n${section}:\n  ${key}: ${yamlScalar(value)}\n`;
  let end = lines.length;
  for (let index = sectionIndex + 1; index < lines.length; index += 1) {
    if (lines[index] && !/^\s/.test(lines[index])) {
      end = index;
      break;
    }
  }
  const keyPattern = new RegExp(`^\\s{2}${key}:`);
  const keyIndex = lines
    .slice(sectionIndex + 1, end)
    .findIndex((line) => keyPattern.test(line));
  const replacement = `  ${key}: ${yamlScalar(value)}`;
  if (keyIndex >= 0) {
    lines[sectionIndex + 1 + keyIndex] = replacement;
  } else {
    lines.splice(sectionIndex + 1, 0, replacement);
  }
  return lines.join("\n");
}

function statusLabel(status: string): string {
  return (
    {
      queued: "等待开始",
      running: "正在运行",
      completed: "已完成",
      failed: "运行失败",
      cancelled: "已取消",
    }[status] ?? status
  );
}

function statusTone(
  status: string,
): "good" | "warn" | "bad" | "neutral" {
  if (status === "completed") return "good";
  if (status === "failed") return "bad";
  if (status === "queued" || status === "running") return "warn";
  return "neutral";
}

export function WorkflowBuilder() {
  const [activity, setActivity] = useState<Activity>("train");
  const [serviceBaseUrl, setServiceBaseUrl] = useState("");
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [catalog, setCatalog] = useState<ConfigCatalogEntry[]>([]);
  const [configPath, setConfigPath] = useState("");
  const [templateYaml, setTemplateYaml] = useState("");
  const [loadingTemplate, setLoadingTemplate] = useState(false);

  const [strategyName, setStrategyName] = useState("my-first-strategy");
  const [datasetPath, setDatasetPath] = useState("data/sample");
  const [algorithm, setAlgorithm] = useState<Algorithm>("PPO");
  const [timesteps, setTimesteps] = useState(128);
  const [initialCash, setInitialCash] = useState(1_000_000);
  const [riskProfile, setRiskProfile] =
    useState<RiskProfile>("balanced");
  const [maxAssetWeight, setMaxAssetWeight] = useState(30);
  const [cashFloor, setCashFloor] = useState(10);
  const [maxTurnover, setMaxTurnover] = useState(35);
  const [maxDrawdown, setMaxDrawdown] = useState(25);
  const [transactionCostBps, setTransactionCostBps] = useState(10);
  const [slippageBps, setSlippageBps] = useState(5);
  const [allowShort, setAllowShort] = useState(false);

  const [runId, setRunId] = useState("my-first-strategy");
  const [partition, setPartition] =
    useState<"validation" | "test">("validation");
  const [testAcknowledged, setTestAcknowledged] = useState(false);

  const [studyName, setStudyName] = useState("my-parameter-search");
  const [searcher, setSearcher] = useState("pso");
  const [scheduler, setScheduler] = useState("asha");
  const [maxTrials, setMaxTrials] = useState(4);

  const [agentPreset, setAgentPreset] =
    useState<AgentPreset>("full_stack");
  const [agentRunName, setAgentRunName] = useState("my-ai-review");

  const [job, setJob] = useState<JobRecord | null>(null);
  const [jobLog, setJobLog] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("正在连接本地策略服务…");
  const requestGeneration = useRef(0);

  const configKind = activityConfigKind[activity];
  const activeJob = Boolean(job && !terminalStatuses.has(job.status));
  const activeJobId = activeJob ? job?.job_id : null;

  const configuredYaml = useMemo(() => {
    if (!templateYaml) return "";
    let yaml = templateYaml;
    if (activity === "train") {
      yaml = setTopLevel(
        yaml,
        "run_name",
        portableName(strategyName, "my-strategy"),
      );
      yaml = setTopLevel(yaml, "dataset_root", datasetPath.trim() || "data/sample");
      yaml = setSectionValue(yaml, "trainer", "algorithm", algorithm);
      yaml = setSectionValue(yaml, "trainer", "total_timesteps", timesteps);
      yaml = setSectionValue(yaml, "environment", "initial_cash", initialCash);
      yaml = setSectionValue(
        yaml,
        "environment",
        "max_asset_weight",
        maxAssetWeight / 100,
      );
      yaml = setSectionValue(
        yaml,
        "environment",
        "cash_floor",
        cashFloor / 100,
      );
      yaml = setSectionValue(
        yaml,
        "environment",
        "max_turnover",
        maxTurnover / 100,
      );
      yaml = setSectionValue(yaml, "environment", "allow_short", allowShort);
      yaml = setSectionValue(
        yaml,
        "environment",
        "transaction_cost_bps",
        transactionCostBps,
      );
      yaml = setSectionValue(
        yaml,
        "environment",
        "slippage_bps",
        slippageBps,
      );
      yaml = setSectionValue(
        yaml,
        "callbacks",
        "max_drawdown",
        maxDrawdown / 100,
      );
    } else if (activity === "tune") {
      const name = portableName(studyName, "my-parameter-search");
      yaml = setTopLevel(yaml, "study_name", name);
      yaml = setTopLevel(yaml, "storage_path", `runs/tuning/${name}.sqlite3`);
      yaml = setTopLevel(yaml, "max_trials", maxTrials);
      yaml = setSectionValue(yaml, "searcher", "type", searcher);
      yaml = setSectionValue(yaml, "scheduler", "type", scheduler);
    } else if (activity === "agent") {
      yaml = setTopLevel(
        yaml,
        "run_id",
        portableName(agentRunName, "my-ai-review"),
      );
    }
    return yaml;
  }, [
    activity,
    agentRunName,
    algorithm,
    allowShort,
    cashFloor,
    datasetPath,
    initialCash,
    maxAssetWeight,
    maxDrawdown,
    maxTrials,
    maxTurnover,
    scheduler,
    searcher,
    slippageBps,
    strategyName,
    studyName,
    templateYaml,
    timesteps,
    transactionCostBps,
  ]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const requested = new URLSearchParams(window.location.search).get("mode");
      if (requested && activities.some((item) => item.id === requested)) {
        setActivity(requested as Activity);
      }
      const requestedRun = new URLSearchParams(window.location.search).get("run");
      if (requestedRun) setRunId(requestedRun);
      const baseUrl = readServiceBaseUrl();
      setServiceBaseUrl(baseUrl);
      getCapabilities(baseUrl)
        .then((value) => {
          setCapabilities(value);
          setNotice(
            value.execution_enabled
              ? "策略服务已连接，可以开始。"
              : "服务当前只能查看结果，暂时不能启动新任务。",
          );
        })
        .catch((error: unknown) => {
          setCapabilities(null);
          setNotice(friendlyError(error));
        });
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!serviceBaseUrl || !configKind) return;
    const timer = window.setTimeout(() => {
      const generation = ++requestGeneration.current;
      setLoadingTemplate(true);
      listConfigs(serviceBaseUrl, configKind)
        .then((entries) => {
          if (generation !== requestGeneration.current) return;
          setCatalog(entries);
        })
        .catch((error: unknown) => {
          if (generation !== requestGeneration.current) return;
          setCatalog([]);
          setNotice(friendlyError(error));
        })
        .finally(() => {
          if (generation === requestGeneration.current) setLoadingTemplate(false);
        });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [configKind, serviceBaseUrl]);

  useEffect(() => {
    if (!catalog.length || !configKind) return;
    const timer = window.setTimeout(() => {
      let preferred = "";
      if (activity === "train") {
        const wanted =
          algorithm === "PPO"
            ? "ppo_quickstart.yaml"
            : `${algorithm.toLowerCase()}.yaml`;
        preferred =
          catalog.find((entry) => entry.path.endsWith(wanted))?.path ?? "";
      } else if (activity === "tune") {
        preferred =
          catalog.find((entry) =>
            entry.path.endsWith("ppo_pso_quickstart.yaml"),
          )?.path ?? "";
      } else {
        const wanted: Record<AgentPreset, string> = {
          full_stack: "full_stack.yaml",
          team: "runtime_deepseek_team.yaml",
          research: "research_single_mock.yaml",
          offline: "runtime_team_offline.yaml",
        };
        preferred =
          catalog.find((entry) =>
            entry.path.endsWith(wanted[agentPreset]),
          )?.path ?? "";
      }
      setConfigPath(preferred || catalog[0].path);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [activity, agentPreset, algorithm, catalog, configKind]);

  useEffect(() => {
    if (!serviceBaseUrl || !configKind || !configPath) return;
    const timer = window.setTimeout(() => {
      const generation = ++requestGeneration.current;
      setLoadingTemplate(true);
      getConfigContent(serviceBaseUrl, configKind, configPath)
        .then((value) => {
          if (generation !== requestGeneration.current) return;
          setTemplateYaml(value.content);
        })
        .catch((error: unknown) => {
          if (generation !== requestGeneration.current) return;
          setTemplateYaml("");
          setNotice(friendlyError(error));
        })
        .finally(() => {
          if (generation === requestGeneration.current) setLoadingTemplate(false);
        });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [configKind, configPath, serviceBaseUrl]);

  useEffect(() => {
    if (!activeJobId) return;
    let disposed = false;
    const poll = async () => {
      try {
        const [nextJob, nextLog] = await Promise.all([
          getJob(serviceBaseUrl, activeJobId),
          getJobLog(serviceBaseUrl, activeJobId),
        ]);
        if (disposed) return;
        setJob(nextJob);
        setJobLog(nextLog.output);
        setNotice(
          terminalStatuses.has(nextJob.status)
            ? `任务${statusLabel(nextJob.status)}。`
            : `${statusLabel(nextJob.status)}，请保持本页打开。`,
        );
      } catch (error) {
        if (!disposed) setNotice(friendlyError(error));
      }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 1500);
    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, [activeJobId, serviceBaseUrl]);

  function chooseActivity(next: Activity) {
    requestGeneration.current += 1;
    setActivity(next);
    setCatalog([]);
    setConfigPath("");
    setTemplateYaml("");
    setJob(null);
    setJobLog("");
    setTestAcknowledged(false);
  }

  function chooseRiskProfile(next: RiskProfile) {
    const profile = riskProfiles[next];
    setRiskProfile(next);
    setMaxAssetWeight(profile.maxAssetWeight);
    setCashFloor(profile.cashFloor);
    setMaxTurnover(profile.maxTurnover);
    setMaxDrawdown(profile.maxDrawdown);
  }

  function buildRequest(): JobRequest {
    if (activity === "backtest") {
      return {
        kind: "backtest",
        run_id: portableName(runId, "my-strategy"),
        partition,
        acknowledge_locked_test:
          partition === "test" ? testAcknowledged : false,
      };
    }
    if (!configKind) throw new Error("请选择要执行的任务。");
    return {
      kind: configKind,
      config_path: configPath,
      config_yaml: configuredYaml,
    };
  }

  async function startJob() {
    if (!capabilities?.execution_enabled || activeJob) return;
    setBusy(true);
    setJob(null);
    setJobLog("");
    setNotice("正在检查设置…");
    try {
      if (configKind) {
        const validation = await validateConfig(
          serviceBaseUrl,
          configKind,
          configPath,
          configuredYaml,
        );
        if (!validation.valid) {
          setNotice(`设置未通过检查：${validation.errors.join("；")}`);
          return;
        }
      }
      const created = await submitJob(serviceBaseUrl, buildRequest());
      setJob(created);
      setNotice("任务已提交，马上开始运行。");
    } catch (error) {
      setNotice(`无法启动：${friendlyError(error)}`);
    } finally {
      setBusy(false);
    }
  }

  async function stopJob() {
    if (!job || terminalStatuses.has(job.status)) return;
    setBusy(true);
    try {
      const cancelled = await cancelJob(serviceBaseUrl, job.job_id);
      setJob(cancelled);
      setNotice("任务已取消。");
    } catch (error) {
      setNotice(`无法取消：${friendlyError(error)}`);
    } finally {
      setBusy(false);
    }
  }

  const startDisabled =
    busy ||
    activeJob ||
    !capabilities?.execution_enabled ||
    Boolean(configKind && (!configPath || !configuredYaml || loadingTemplate)) ||
    (activity === "backtest" && !portableName(runId, "")) ||
    (activity === "backtest" &&
      partition === "test" &&
      !testAcknowledged);

  return (
    <>
      {!capabilities?.execution_enabled && (
        <section className="alert alert-warn consumer-alert">
          <div className="alert-mark">!</div>
          <div>
            <strong>策略服务尚未连接</strong>
            <p>{notice}</p>
          </div>
          <Link className="button secondary" href="/settings">
            检查连接
          </Link>
        </section>
      )}

      <section className="activity-grid" aria-label="选择操作">
        {activities.map((item) => (
          <button
            type="button"
            className={`activity-card ${activity === item.id ? "selected" : ""}`}
            onClick={() => chooseActivity(item.id)}
            aria-pressed={activity === item.id}
            key={item.id}
          >
            <span>{item.mark}</span>
            <strong>{item.label}</strong>
            <small>{item.note}</small>
          </button>
        ))}
      </section>

      <div className="strategy-layout">
        <section className="panel strategy-form">
          {activity === "train" && (
            <>
              <div className="strategy-section">
                <div className="section-number">1</div>
                <div className="section-body">
                  <h2>给策略起个名字</h2>
                  <p>名称只用于查找结果，建议使用英文、数字或短横线。</p>
                  <div className="form-grid">
                    <label className="field">
                      <span>策略名称</span>
                      <input
                        value={strategyName}
                        onChange={(event) => setStrategyName(event.target.value)}
                        spellCheck={false}
                      />
                    </label>
                    <label className="field">
                      <span>数据目录</span>
                      <input
                        value={datasetPath}
                        onChange={(event) => setDatasetPath(event.target.value)}
                        spellCheck={false}
                      />
                      <small>首次体验请保留 data/sample。</small>
                    </label>
                  </div>
                </div>
              </div>

              <div className="strategy-section">
                <div className="section-number">2</div>
                <div className="section-body">
                  <h2>选择学习方式</h2>
                  <p>不确定时选择 PPO，它稳定、容易上手，适合第一次训练。</p>
                  <div className="choice-grid three">
                    {[
                      ["PPO", "推荐", "稳定易用，适合大多数场景"],
                      ["SAC", "连续决策", "探索更充分，训练时间较长"],
                      ["TD3", "高级", "适合连续仓位和自定义特征"],
                    ].map(([value, badge, note]) => (
                      <button
                        type="button"
                        className={algorithm === value ? "selected" : ""}
                        onClick={() => setAlgorithm(value as Algorithm)}
                        key={value}
                      >
                        <span>{badge}</span>
                        <strong>{value}</strong>
                        <small>{note}</small>
                      </button>
                    ))}
                  </div>
                  <label className="field range-field">
                    <span>
                      训练强度 <strong>{timesteps.toLocaleString()} 步</strong>
                    </span>
                    <input
                      type="range"
                      min={128}
                      max={8192}
                      step={128}
                      value={timesteps}
                      onChange={(event) => setTimesteps(Number(event.target.value))}
                    />
                    <small>步数越多耗时越长。内置样本建议从 128 步开始。</small>
                  </label>
                </div>
              </div>

              <div className="strategy-section">
                <div className="section-number">3</div>
                <div className="section-body">
                  <h2>选择风险偏好</h2>
                  <p>这些限制会在每次模拟交易前生效，AI 也不能绕过。</p>
                  <div className="choice-grid three">
                    {(Object.keys(riskProfiles) as RiskProfile[]).map((key) => {
                      const profile = riskProfiles[key];
                      return (
                        <button
                          type="button"
                          className={riskProfile === key ? "selected" : ""}
                          onClick={() => chooseRiskProfile(key)}
                          key={key}
                        >
                          <strong>{profile.label}</strong>
                          <small>{profile.note}</small>
                        </button>
                      );
                    })}
                  </div>
                  <div className="form-grid risk-fields">
                    <label className="field">
                      <span>模拟初始资金</span>
                      <input
                        type="number"
                        min={1000}
                        step={1000}
                        value={initialCash}
                        onChange={(event) =>
                          setInitialCash(Math.max(1000, Number(event.target.value)))
                        }
                      />
                    </label>
                    <label className="field">
                      <span>单一资产上限（%）</span>
                      <input
                        type="number"
                        min={1}
                        max={100}
                        value={maxAssetWeight}
                        onChange={(event) =>
                          setMaxAssetWeight(Number(event.target.value))
                        }
                      />
                    </label>
                    <label className="field">
                      <span>最低现金比例（%）</span>
                      <input
                        type="number"
                        min={0}
                        max={100}
                        value={cashFloor}
                        onChange={(event) =>
                          setCashFloor(Number(event.target.value))
                        }
                      />
                    </label>
                    <label className="field">
                      <span>单次最大换手（%）</span>
                      <input
                        type="number"
                        min={1}
                        max={100}
                        value={maxTurnover}
                        onChange={(event) =>
                          setMaxTurnover(Number(event.target.value))
                        }
                      />
                    </label>
                    <label className="field">
                      <span>最大回撤保护（%）</span>
                      <input
                        type="number"
                        min={1}
                        max={100}
                        value={maxDrawdown}
                        onChange={(event) =>
                          setMaxDrawdown(Number(event.target.value))
                        }
                      />
                    </label>
                    <label className="toggle-row friendly-toggle">
                      <input
                        type="checkbox"
                        checked={allowShort}
                        onChange={(event) => setAllowShort(event.target.checked)}
                      />
                      允许做空
                    </label>
                  </div>
                </div>
              </div>

              <div className="strategy-section">
                <div className="section-number">4</div>
                <div className="section-body">
                  <h2>确认并开始训练</h2>
                  <div className="review-grid">
                    <div>
                      <span>算法</span>
                      <strong>{algorithm}</strong>
                    </div>
                    <div>
                      <span>风险偏好</span>
                      <strong>{riskProfiles[riskProfile].label}</strong>
                    </div>
                    <div>
                      <span>最低现金</span>
                      <strong>{cashFloor}%</strong>
                    </div>
                    <div>
                      <span>最大回撤</span>
                      <strong>{maxDrawdown}%</strong>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}

          {activity === "backtest" && (
            <div className="strategy-section single">
              <div className="section-number">✓</div>
              <div className="section-body">
                <h2>选择要检验的策略</h2>
                <p>输入训练时使用的策略名称。首次回测建议选择“日常验证”。</p>
                <div className="form-grid">
                  <label className="field full-field">
                    <span>策略名称</span>
                    <input
                      value={runId}
                      onChange={(event) => setRunId(event.target.value)}
                      spellCheck={false}
                    />
                  </label>
                  <label className="field full-field">
                    <span>回测方式</span>
                    <div className="choice-grid two">
                      <button
                        type="button"
                        className={partition === "validation" ? "selected" : ""}
                        onClick={() => {
                          setPartition("validation");
                          setTestAcknowledged(false);
                        }}
                      >
                        <span>推荐</span>
                        <strong>日常验证</strong>
                        <small>可反复运行，不影响最终检验</small>
                      </button>
                      <button
                        type="button"
                        className={partition === "test" ? "selected" : ""}
                        onClick={() => setPartition("test")}
                      >
                        <strong>最终留出区间</strong>
                        <small>确定策略后只运行一次</small>
                      </button>
                    </div>
                  </label>
                </div>
                {partition === "test" && (
                  <div className="alert alert-warn compact-alert">
                    <div className="alert-mark">!</div>
                    <div>
                      <strong>最终区间不是日常调参工具</strong>
                      <p>
                        查看后就不应再根据结果修改策略，否则会高估真实表现。
                      </p>
                      <label className="ack-row">
                        <input
                          type="checkbox"
                          checked={testAcknowledged}
                          onChange={(event) =>
                            setTestAcknowledged(event.target.checked)
                          }
                        />
                        我已完成策略选择，确认运行一次最终检验
                      </label>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {activity === "tune" && (
            <div className="strategy-section single">
              <div className="section-number">✦</div>
              <div className="section-body">
                <h2>让系统自动寻找更好的参数</h2>
                <p>
                  优化只比较训练和验证数据，不会查看最终测试区间。
                  第一次使用建议保留“粒子群 + ASHA”。
                </p>
                <div className="form-grid">
                  <label className="field full-field">
                    <span>优化任务名称</span>
                    <input
                      value={studyName}
                      onChange={(event) => setStudyName(event.target.value)}
                      spellCheck={false}
                    />
                  </label>
                  <label className="field">
                    <span>参数搜索方法</span>
                    <select
                      value={searcher}
                      onChange={(event) => {
                        const next = event.target.value;
                        setSearcher(next);
                        if (
                          scheduler === "pbt" &&
                          ["grid", "simulated_annealing"].includes(next)
                        ) {
                          setScheduler("asha");
                        }
                      }}
                    >
                      {(capabilities?.searchers ?? Object.keys(searcherLabels)).map(
                        (value) => (
                          <option value={value} key={value}>
                            {searcherLabels[value] ?? value}
                          </option>
                        ),
                      )}
                    </select>
                  </label>
                  <label className="field">
                    <span>计算资源分配</span>
                    <select
                      value={scheduler}
                      onChange={(event) => setScheduler(event.target.value)}
                    >
                      {(capabilities?.schedulers ?? Object.keys(schedulerLabels))
                        .filter(
                          (value) =>
                            value !== "pbt" ||
                            !["grid", "simulated_annealing"].includes(searcher),
                        )
                        .map((value) => (
                          <option value={value} key={value}>
                            {schedulerLabels[value] ?? value}
                          </option>
                        ))}
                    </select>
                  </label>
                  <label className="field full-field range-field">
                    <span>
                      尝试组合数 <strong>{maxTrials} 组</strong>
                    </span>
                    <input
                      type="range"
                      min={4}
                      max={24}
                      step={2}
                      value={maxTrials}
                      onChange={(event) =>
                        setMaxTrials(Number(event.target.value))
                      }
                    />
                    <small>组合越多，找到合适参数的机会越高，耗时也越长。</small>
                  </label>
                </div>
              </div>
            </div>
          )}

          {activity === "agent" && (
            <div className="strategy-section single">
              <div className="section-number">AI</div>
              <div className="section-body">
                <h2>选择 AI 顾问团队</h2>
                <p>
                  AI 只提供研究和风险建议，无法直接下单或修改模拟账户。
                </p>
                <label className="field">
                  <span>分析任务名称</span>
                  <input
                    value={agentRunName}
                    onChange={(event) => setAgentRunName(event.target.value)}
                    spellCheck={false}
                  />
                </label>
                <div className="choice-grid two agent-choices">
                  {[
                    [
                      "full_stack",
                      "完整策略团队",
                      "研究分析 + 风险委员会 + 市场状态判断",
                      "推荐",
                    ],
                    [
                      "team",
                      "多专家讨论",
                      "由协调员汇总多名专家意见",
                      "DeepSeek",
                    ],
                    [
                      "research",
                      "单人研究助手",
                      "快速体验数据检查和研究计划",
                      "离线示例",
                    ],
                    [
                      "offline",
                      "离线团队演示",
                      "不调用网络，适合先熟悉流程",
                      "无需密钥",
                    ],
                  ].map(([value, label, note, badge]) => (
                    <button
                      type="button"
                      className={agentPreset === value ? "selected" : ""}
                      onClick={() => setAgentPreset(value as AgentPreset)}
                      key={value}
                    >
                      <span>{badge}</span>
                      <strong>{label}</strong>
                      <small>{note}</small>
                    </button>
                  ))}
                </div>
                <div className="ai-boundary">
                  <span>自动保护</span>
                  <p>
                    顾问建议会经过仓位上限、现金比例、换手限制和市场权重检查。
                  </p>
                </div>
              </div>
            </div>
          )}

          {configKind && (
            <details className="advanced-config">
              <summary>高级设置</summary>
              <p>
                通常无需修改。这里显示系统生成配置的基础模板，适合熟悉
                CrossMarketAgentGym 的用户。
              </p>
              <label className="field">
                <span>基础模板</span>
                <select
                  value={configPath}
                  onChange={(event) => setConfigPath(event.target.value)}
                >
                  {catalog.map((entry) => (
                    <option value={entry.path} key={entry.path}>
                      {entry.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>YAML</span>
                <textarea
                  value={templateYaml}
                  onChange={(event) => setTemplateYaml(event.target.value)}
                  spellCheck={false}
                />
              </label>
            </details>
          )}

          <div className="start-bar">
            <div>
              <strong>
                {activity === "train"
                  ? "准备训练策略"
                  : activity === "backtest"
                    ? "准备运行历史回测"
                    : activity === "tune"
                      ? "准备优化参数"
                      : "准备启动 AI 分析"}
              </strong>
              <small>
                点击后系统会先检查设置，通过后才会开始运行。
              </small>
            </div>
            <button
              type="button"
              className="button primary start-button"
              disabled={startDisabled}
              onClick={() => void startJob()}
            >
              {busy
                ? "正在检查…"
                : activeJob
                  ? "任务运行中"
                  : !capabilities?.execution_enabled
                    ? "服务未连接"
                    : activity === "train"
                      ? "开始训练"
                      : activity === "backtest"
                        ? "开始回测"
                        : activity === "tune"
                          ? "开始优化"
                          : "开始分析"}
            </button>
          </div>
        </section>

        <aside className="panel strategy-summary">
          <div className="tiny-label">本次操作</div>
          <h2>{activities.find((item) => item.id === activity)?.label}</h2>
          {activity === "train" && (
            <dl>
              <div>
                <dt>策略</dt>
                <dd>{portableName(strategyName, "my-strategy")}</dd>
              </div>
              <div>
                <dt>数据</dt>
                <dd>{datasetPath}</dd>
              </div>
              <div>
                <dt>算法</dt>
                <dd>{algorithm}</dd>
              </div>
              <div>
                <dt>风险</dt>
                <dd>{riskProfiles[riskProfile].label}</dd>
              </div>
              <div>
                <dt>交易成本</dt>
                <dd>
                  <input
                    aria-label="交易成本基点"
                    type="number"
                    min={0}
                    value={transactionCostBps}
                    onChange={(event) =>
                      setTransactionCostBps(Number(event.target.value))
                    }
                  />{" "}
                  bps
                </dd>
              </div>
              <div>
                <dt>滑点</dt>
                <dd>
                  <input
                    aria-label="滑点基点"
                    type="number"
                    min={0}
                    value={slippageBps}
                    onChange={(event) =>
                      setSlippageBps(Number(event.target.value))
                    }
                  />{" "}
                  bps
                </dd>
              </div>
            </dl>
          )}
          <div className="summary-note">
            <span>✓</span>
            <p>
              所有操作仅作用于历史模拟环境，不会连接券商或真实资金账户。
            </p>
          </div>
          <p className="service-note">{notice}</p>
        </aside>
      </div>

      {job && (
        <section className="panel progress-panel" aria-live="polite">
          <div className="panel-head">
            <div>
              <div className="tiny-label">运行进度</div>
              <h2>{statusLabel(job.status)}</h2>
            </div>
            <StatusPill tone={statusTone(job.status)}>
              {statusLabel(job.status)}
            </StatusPill>
          </div>
          <div className="progress-track" aria-hidden="true">
            <i
              className={
                job.status === "completed"
                  ? "complete"
                  : job.status === "failed"
                    ? "failed"
                    : ""
              }
            />
          </div>
          <p>
            {job.status === "completed"
              ? "运行完成。你可以前往回测记录查看结果。"
              : job.status === "failed"
                ? "运行没有完成，请展开详细信息查看原因。"
                : "后台正在处理数据和模型，请保持服务运行。"}
          </p>
          <div className="progress-actions">
            {job.status === "completed" && (
              <>
                <Link className="button primary" href="/runs">
                  查看结果
                </Link>
                {activity === "train" && (
                  <button
                    className="button secondary"
                    type="button"
                    onClick={() => {
                      setRunId(portableName(strategyName, "my-strategy"));
                      chooseActivity("backtest");
                    }}
                  >
                    回测这个策略
                  </button>
                )}
              </>
            )}
            {!terminalStatuses.has(job.status) && (
              <button
                className="button secondary"
                type="button"
                onClick={() => void stopJob()}
                disabled={busy}
              >
                取消运行
              </button>
            )}
          </div>
          <details className="run-details">
            <summary>查看运行详情</summary>
            <p>任务编号：{job.job_id}</p>
            {job.error && <p className="error-text">{job.error}</p>}
            <pre className="job-log">
              {jobLog || "任务正在启动，暂时没有详细信息。"}
            </pre>
          </details>
        </section>
      )}
    </>
  );
}
