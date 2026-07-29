"use client";

import { useEffect, useState } from "react";
import { StatusPill } from "../components/AppShell";
import {
  DEFAULT_SERVICE_BASE_URL,
  SERVICE_BASE_URL_STORAGE_KEY,
  getCapabilities,
  normalizeServiceBaseUrl,
  readServiceBaseUrl,
  type Capabilities,
} from "../lib/api";

const densityStorageKey = "cmag.interfaceDensity";

type ProbeState = "idle" | "checking" | "connected" | "failed";

type HealthPayload = {
  status?: string;
  version?: string;
  workspace?: string;
  execution_enabled?: boolean;
};

export function SettingsPanel() {
  const [baseUrl, setBaseUrl] = useState(DEFAULT_SERVICE_BASE_URL);
  const [density, setDensity] = useState("comfortable");
  const [probeState, setProbeState] = useState<ProbeState>("idle");
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [message, setMessage] = useState("点击“测试连接”检查服务状态。");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setBaseUrl(readServiceBaseUrl());
      setDensity(window.localStorage.getItem(densityStorageKey) || "comfortable");
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  async function probe() {
    setProbeState("checking");
    setHealth(null);
    setCapabilities(null);
    setMessage("正在连接本地策略服务…");
    try {
      const normalized = normalizeServiceBaseUrl(baseUrl);
      const [healthResponse, capabilityResponse] = await Promise.all([
        fetch(`${normalized}/health`, {
          headers: { Accept: "application/json" },
        }),
        getCapabilities(normalized),
      ]);
      if (!healthResponse.ok) throw new Error(`服务返回 ${healthResponse.status}`);
      const healthPayload = (await healthResponse.json()) as HealthPayload;
      setHealth(healthPayload);
      setCapabilities(capabilityResponse);
      setProbeState("connected");
      setMessage(
        capabilityResponse.execution_enabled
          ? "连接成功，可以训练和回测策略。"
          : "连接成功，但当前服务仅允许查看结果。",
      );
    } catch (error) {
      setProbeState("failed");
      setMessage(
        error instanceof Error
          ? `连接失败：${error.message}`
          : "连接失败，请确认本地服务已经启动。",
      );
    }
  }

  function save() {
    try {
      const normalized = normalizeServiceBaseUrl(baseUrl);
      window.localStorage.setItem(SERVICE_BASE_URL_STORAGE_KEY, normalized);
      window.localStorage.setItem(densityStorageKey, density);
      document.documentElement.dataset.density = density;
      setBaseUrl(normalized);
      setMessage("设置已保存在当前浏览器。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "无法保存设置。");
    }
  }

  const aiReady =
    capabilities?.dependencies.deepseek_api_key_configured === true;
  const trainingReady =
    capabilities?.execution_enabled &&
    capabilities.dependencies.torch &&
    capabilities.dependencies.stable_baselines3;

  return (
    <div className="consumer-settings">
      <section className="panel connection-card">
        <div className="panel-head">
          <div>
            <div className="tiny-label">服务连接</div>
            <h2>本地策略服务</h2>
          </div>
          <StatusPill
            tone={
              probeState === "connected"
                ? "good"
                : probeState === "failed"
                  ? "bad"
                  : probeState === "checking"
                    ? "warn"
                    : "neutral"
            }
          >
            {probeState === "connected"
              ? "已连接"
              : probeState === "failed"
                ? "未连接"
                : probeState === "checking"
                  ? "连接中"
                  : "待检查"}
          </StatusPill>
        </div>

        <label className="field full-field">
          <span>服务地址</span>
          <input
            value={baseUrl}
            onChange={(event) => {
              setBaseUrl(event.target.value);
              setProbeState("idle");
            }}
            inputMode="url"
            spellCheck={false}
          />
          <small>
            使用本机默认安装时无需修改。网页只保存这个地址，不保存任何密钥。
          </small>
        </label>

        <div className="setting-actions">
          <button
            className="button secondary"
            type="button"
            onClick={() => void probe()}
            disabled={probeState === "checking"}
          >
            {probeState === "checking" ? "正在连接…" : "测试连接"}
          </button>
          <button className="button primary" type="button" onClick={save}>
            保存设置
          </button>
        </div>
        <p className="connection-message" role="status">
          {message}
        </p>
      </section>

      <section className="readiness-grid" aria-label="功能状态">
        <article className="panel readiness-card">
          <span className={trainingReady ? "ready-mark" : "waiting-mark"}>
            {trainingReady ? "✓" : "—"}
          </span>
          <div>
            <h2>策略训练与回测</h2>
            <p>
              {trainingReady
                ? "训练组件已经准备好。"
                : "连接服务后可检查训练组件。"}
            </p>
          </div>
          <StatusPill tone={trainingReady ? "good" : "neutral"}>
            {trainingReady ? "可用" : "待检查"}
          </StatusPill>
        </article>

        <article className="panel readiness-card">
          <span className={aiReady ? "ready-mark" : "waiting-mark"}>
            {aiReady ? "✓" : "—"}
          </span>
          <div>
            <h2>AI 策略顾问</h2>
            <p>
              {aiReady
                ? "DeepSeek 顾问已经配置。"
                : "未检测到 AI 服务配置，离线演示仍可使用。"}
            </p>
          </div>
          <StatusPill tone={aiReady ? "good" : "neutral"}>
            {aiReady ? "可用" : "未配置"}
          </StatusPill>
        </article>

        <article className="panel readiness-card">
          <span className="ready-mark">✓</span>
          <div>
            <h2>模拟交易保护</h2>
            <p>AI 无法直接下单，所有动作都会经过风险检查。</p>
          </div>
          <StatusPill tone="good">已开启</StatusPill>
        </article>
      </section>

      {capabilities && (
        <section className="panel capability-card">
          <div>
            <div className="tiny-label">当前可用</div>
            <h2>策略功能</h2>
          </div>
          <div className="capability-chips">
            {capabilities.algorithms.map((value) => (
              <span key={value}>{value}</span>
            ))}
            <span>{capabilities.searchers.length} 种参数搜索</span>
            <span>{capabilities.agent_model} AI 顾问</span>
          </div>
        </section>
      )}

      <section className="panel preference-card">
        <div className="setting-section">
          <div>
            <h2>界面显示</h2>
            <p>选择你喜欢的信息密度，只影响当前浏览器。</p>
          </div>
          <div className="segmented" role="group" aria-label="界面密度">
            {[
              ["comfortable", "舒适"],
              ["compact", "紧凑"],
            ].map(([value, label]) => (
              <button
                type="button"
                className={density === value ? "selected" : ""}
                aria-pressed={density === value}
                onClick={() => setDensity(value)}
                key={value}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </section>

      <details className="panel help-details">
        <summary>服务无法连接时怎么办？</summary>
        <p>
          请确认 CrossMarketAgentGym 已安装，并在项目目录启动本地 GUI 服务。
          高级用户可使用下面的命令：
        </p>
        <code>cmag service run --config configs/reporting/gui.yaml</code>
        {health && (
          <p>
            当前版本：{health.version || "未知"} · 工作区：
            {health.workspace || "未知"}
          </p>
        )}
      </details>
    </div>
  );
}
