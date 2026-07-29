"use client";

import { useEffect, useState } from "react";
import { StatusPill } from "../components/AppShell";

const defaultUrl = "http://127.0.0.1:8000";

export function SettingsPanel() {
  const [baseUrl, setBaseUrl] = useState(defaultUrl);
  const [density, setDensity] = useState("comfortable");
  const [probeState, setProbeState] = useState<
    "idle" | "checking" | "online" | "offline"
  >("idle");
  const [message, setMessage] = useState("尚未探测只读服务。");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const stored = window.localStorage.getItem("cmag.reportBaseUrl");
      const storedDensity = window.localStorage.getItem("cmag.density");
      if (stored) setBaseUrl(stored);
      if (storedDensity) setDensity(storedDensity);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  function save() {
    try {
      const parsed = new URL(baseUrl);
      if (!["http:", "https:"].includes(parsed.protocol)) throw new Error();
      if (parsed.username || parsed.password) {
        setMessage("地址中不得包含用户名或密码。");
        return;
      }
      window.localStorage.setItem(
        "cmag.reportBaseUrl",
        parsed.toString().replace(/\/$/, ""),
      );
      window.localStorage.setItem("cmag.density", density);
      setMessage("设置已保存在当前浏览器。");
    } catch {
      setMessage("请输入有效的 HTTP(S) 服务地址。");
    }
  }

  async function probe() {
    setProbeState("checking");
    setMessage("正在请求 /health…");
    try {
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 5000);
      const response = await fetch(
        `${baseUrl.replace(/\/$/, "")}/health`,
        { signal: controller.signal },
      );
      window.clearTimeout(timeout);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setProbeState("online");
      setMessage("只读服务健康检查通过。");
    } catch {
      setProbeState("offline");
      setMessage(
        "无法从浏览器访问服务。请确认 cmag serve 已启动、地址正确且允许当前 Origin；托管 HTTPS 页面无法访问不安全的 HTTP 服务。",
      );
    }
  }

  return (
    <div className="settings-layout">
      <section className="panel settings-main">
        <div className="panel-head">
          <div>
            <div className="tiny-label">Read-only report service</div>
            <h2>本地服务连接</h2>
          </div>
          <StatusPill
            tone={
              probeState === "online"
                ? "good"
                : probeState === "offline"
                  ? "bad"
                  : "neutral"
            }
          >
            {probeState}
          </StatusPill>
        </div>

        <label className="field full-field">
          <span>服务 Base URL</span>
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
            对应 <code>cmag serve --host 127.0.0.1 --port 8000</code>。
            服务只公开健康、运行索引和报告资产。
          </small>
        </label>

        <div className="setting-actions">
          <button
            className="button secondary"
            type="button"
            onClick={probe}
            disabled={probeState === "checking"}
          >
            {probeState === "checking" ? "正在探测…" : "探测 /health"}
          </button>
          <button className="button primary" type="button" onClick={save}>
            保存本地设置
          </button>
        </div>
        <p className="inline-notice" role="status">
          {message}
        </p>

        <hr />

        <div className="setting-section">
          <div>
            <h3>界面密度</h3>
            <p>偏好只影响当前浏览器，不改变报告与实验配置。</p>
          </div>
          <div className="segmented" role="group" aria-label="界面密度">
            {[
              ["comfortable", "舒适"],
              ["compact", "紧凑"],
            ].map(([value, label]) => (
              <button
                type="button"
                className={density === value ? "selected" : undefined}
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

      <aside className="panel secrets-card">
        <div className="tiny-label">Credential boundary</div>
        <h2>浏览器中没有密钥</h2>
        <p>
          DeepSeek API Key、远程 SSH 凭据和 GitHub 凭据都不属于前端配置。
          Agent 运行必须从后端环境变量读取密钥并写入审计日志中的脱敏状态。
        </p>
        <div className="secret-rule">
          <span>前端</span>
          <strong>只读 URL + 报告 JSON</strong>
        </div>
        <div className="secret-rule">
          <span>受控终端</span>
          <strong>CLI 命令 + 环境变量</strong>
        </div>
        <div className="secret-rule">
          <span>环境</span>
          <strong>确定性账户状态</strong>
        </div>
        <div className="alert alert-good compact-alert">
          <div className="alert-mark">✓</div>
          <div>
            <strong>安全默认值</strong>
            <p>不上传、不显示、不持久化任何模型或服务器凭据。</p>
          </div>
        </div>
      </aside>
    </div>
  );
}
