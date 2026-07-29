"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { StatusPill } from "../components/AppShell";

const defaultServiceUrl = "http://127.0.0.1:8000";
const serviceUrlStorageKey = "cmag.serviceBaseUrl";

type RecentJob = {
  jobId: string;
  kind: string;
  status: string;
  runId: string | null;
  createdAt: string;
};

type DisplayRun = {
  id: string;
  kind: string;
  status: "good" | "pending" | "failed";
  sourceStatus: string;
  dataset: string;
  createdAt: string;
  summary: string;
  reproduction: string;
  protocol: string;
  fingerprint: string;
  artifactCount: number | null;
};

const kindLabels: Record<string, string> = {
  train: "策略训练",
  training: "策略训练",
  backtest: "历史回测",
  tune: "参数优化",
  tuning: "参数优化",
  agent: "AI 顾问分析",
  report: "结果报告",
  reproduce: "结果复核",
  data_validate: "数据检查",
  environment_check: "环境检查",
};

const statusLabels: Record<string, string> = {
  queued: "等待开始",
  running: "正在运行",
  completed: "已完成",
  verified: "已验证",
  numerically_reproduced: "已复核",
  provisional: "可查看",
  failed: "失败",
  cancelled: "已取消",
};

function objectValue(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null
    ? (value as Record<string, unknown>)
    : {};
}

function runStatus(status: string): "good" | "pending" | "failed" {
  const normalized = status.toLowerCase();
  if (
    normalized.includes("fail") ||
    normalized.includes("error") ||
    normalized === "cancelled"
  ) {
    return "failed";
  }
  if (
    normalized.includes("verified") ||
    normalized.includes("reproduced") ||
    normalized === "completed"
  ) {
    return "good";
  }
  return "pending";
}

function statusLabel(value: string): string {
  return statusLabels[value.toLowerCase()] ?? value;
}

function kindLabel(value: string): string {
  const lower = value.toLowerCase();
  return (
    Object.entries(kindLabels).find(([key]) => lower.includes(key))?.[1] ??
    value
  );
}

function formatDate(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value.replace(/^Phase\s*/i, "历史记录 ")
    : new Intl.DateTimeFormat("zh-CN", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(parsed);
}

function normalizeRuns(value: unknown): DisplayRun[] {
  const payload = objectValue(value);
  const candidate = Array.isArray(value) ? value : payload.runs;
  if (!Array.isArray(candidate)) throw new Error("服务没有返回运行记录。");
  return candidate.slice(0, 500).map((item, index) => {
    const row = objectValue(item);
    const attributes = objectValue(row.attributes);
    const sourceStatus = String(row.status ?? "provisional");
    const partitions = Array.isArray(row.partitions)
      ? row.partitions.map(String)
      : [];
    const relativePath = String(row.relative_path ?? "");
    const artifactCount =
      typeof row.artifact_count === "number" ? row.artifact_count : null;
    return {
      id: String(row.run_id ?? row.id ?? `run-${index + 1}`),
      kind: kindLabel(
        `${String(row.algorithm ?? "")} ${String(row.kind ?? "策略运行")}`.trim(),
      ),
      status: runStatus(sourceStatus),
      sourceStatus,
      dataset: String(
        row.dataset ??
          row.dataset_manifest_hash ??
          attributes.dataset_manifest_hash ??
          "使用运行时数据",
      ),
      createdAt: String(
        row.created_at ?? row.finished_at ?? attributes.finished_at ?? relativePath,
      ),
      summary: String(
        row.summary ??
          `${partitions.length ? `包含 ${partitions.join("、")} 区间` : "策略运行"}${
            artifactCount == null ? "" : `，保存了 ${artifactCount} 项结果`
          }。`,
      ),
      reproduction: String(
        row.reproduction_level ??
          attributes.reproduction_level ??
          "未执行额外复核",
      ),
      protocol: String(
        row.protocol ??
          row.protocol_id ??
          attributes.protocol ??
          attributes.protocol_id ??
          "默认设置",
      ),
      fingerprint: String(row.fingerprint ?? "未报告"),
      artifactCount,
    };
  });
}

function normalizeJobs(value: unknown): RecentJob[] {
  const payload = objectValue(value);
  if (!Array.isArray(payload.jobs)) return [];
  return payload.jobs.slice(0, 12).map((item, index) => {
    const row = objectValue(item);
    return {
      jobId: String(row.job_id ?? `job-${index + 1}`),
      kind: String(row.kind ?? "run"),
      status: String(row.status ?? "queued"),
      runId: row.run_id == null ? null : String(row.run_id),
      createdAt: String(row.created_at ?? ""),
    };
  });
}

function serviceBaseUrl(): string {
  const stored = window.localStorage.getItem(serviceUrlStorageKey);
  return (stored || defaultServiceUrl).replace(/\/$/, "");
}

async function fetchJson(url: string, signal: AbortSignal): Promise<unknown> {
  const response = await fetch(url, {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`服务返回 ${response.status}`);
  return response.json() as Promise<unknown>;
}

function pillTone(
  status: string,
): "good" | "warn" | "bad" | "neutral" {
  const normalized = status.toLowerCase();
  if (
    normalized === "completed" ||
    normalized.includes("verified") ||
    normalized.includes("reproduced")
  )
    return "good";
  if (normalized === "failed" || normalized === "cancelled") return "bad";
  if (normalized === "queued" || normalized === "running") return "warn";
  return "neutral";
}

export function RunExplorer() {
  const [runs, setRuns] = useState<DisplayRun[]>([]);
  const [jobs, setJobs] = useState<RecentJob[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState("正在读取策略记录…");
  const fileRef = useRef<HTMLInputElement>(null);

  const loadServiceData = useCallback(async () => {
    setLoading(true);
    const baseUrl = serviceBaseUrl();
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 8000);
    try {
      const [runsResult, jobsResult] = await Promise.allSettled([
        fetchJson(`${baseUrl}/api/runs?limit=500`, controller.signal),
        fetchJson(`${baseUrl}/api/jobs?limit=20`, controller.signal),
      ]);
      if (runsResult.status === "rejected") throw runsResult.reason;
      const loadedRuns = normalizeRuns(runsResult.value);
      setRuns(loadedRuns);
      setSelectedId((current) =>
        loadedRuns.some((run) => run.id === current)
          ? current
          : (loadedRuns[0]?.id ?? ""),
      );
      setJobs(
        jobsResult.status === "fulfilled"
          ? normalizeJobs(jobsResult.value)
          : [],
      );
      setNotice(`已加载 ${loadedRuns.length} 条策略记录。`);
    } catch (error) {
      setNotice(
        `暂时无法读取本地记录：${
          error instanceof Error ? error.message : "连接失败"
        }。`,
      );
    } finally {
      window.clearTimeout(timeout);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadServiceData(), 0);
    return () => window.clearTimeout(timer);
  }, [loadServiceData]);

  const filtered = useMemo(
    () =>
      runs.filter((run) =>
        `${run.id} ${run.kind}`.toLowerCase().includes(query.toLowerCase()),
      ),
    [query, runs],
  );
  const selected = runs.find((run) => run.id === selectedId) ?? filtered[0];

  async function importFile(file?: File) {
    if (!file) return;
    try {
      const imported = normalizeRuns(JSON.parse(await file.text()) as unknown);
      setRuns(imported);
      setSelectedId(imported[0]?.id ?? "");
      setNotice(`已导入 ${imported.length} 条记录，文件不会上传。`);
    } catch (error) {
      setNotice(
        error instanceof Error ? `导入失败：${error.message}` : "导入失败。",
      );
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <>
      <section className="toolbar panel result-toolbar">
        <label className="search-field">
          <span className="sr-only">搜索策略</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索策略名称或算法…"
          />
        </label>
        <button
          className="button secondary"
          type="button"
          onClick={() => void loadServiceData()}
          disabled={loading}
        >
          {loading ? "读取中…" : "刷新"}
        </button>
        <input
          className="sr-only"
          type="file"
          accept=".json,application/json"
          ref={fileRef}
          onChange={(event) => void importFile(event.target.files?.[0])}
        />
        <button
          className="button ghost"
          type="button"
          onClick={() => fileRef.current?.click()}
        >
          导入记录
        </button>
      </section>
      <p className="inline-notice" role="status">
        {notice}
      </p>

      {jobs.length > 0 && (
        <section className="panel recent-jobs">
          <div className="panel-head">
            <div>
              <div className="tiny-label">正在进行</div>
              <h2>最近启动的任务</h2>
            </div>
          </div>
          <div className="job-chip-row">
            {jobs.slice(0, 6).map((job) => (
              <div className="job-chip" key={job.jobId} title={job.createdAt}>
                <div>
                  <strong>{kindLabel(job.kind)}</strong>
                  <small>{job.runId || job.jobId}</small>
                </div>
                <StatusPill tone={pillTone(job.status)}>
                  {statusLabel(job.status)}
                </StatusPill>
              </div>
            ))}
          </div>
        </section>
      )}

      <div className="result-layout">
        <section className="panel result-list">
          <div className="panel-head">
            <div>
              <div className="tiny-label">全部记录</div>
              <h2>{filtered.length} 个策略</h2>
            </div>
          </div>
          <div className="result-rows">
            {filtered.map((run) => (
              <button
                type="button"
                className={selected?.id === run.id ? "selected" : ""}
                onClick={() => setSelectedId(run.id)}
                key={run.id}
              >
                <div className={`result-icon ${run.status}`}>
                  {run.status === "good"
                    ? "✓"
                    : run.status === "failed"
                      ? "×"
                      : "…"}
                </div>
                <div>
                  <strong>{run.id}</strong>
                  <small>
                    {run.kind} · {formatDate(run.createdAt)}
                  </small>
                </div>
                <span>{statusLabel(run.sourceStatus)}</span>
              </button>
            ))}
            {!loading && filtered.length === 0 && (
              <div className="empty-state friendly-empty">
                <strong>还没有策略记录</strong>
                <p>创建并训练第一套策略后，结果会出现在这里。</p>
                <Link className="button primary" href="/workflows">
                  创建策略
                </Link>
              </div>
            )}
          </div>
        </section>

        <section className="panel result-detail">
          {selected ? (
            <>
              <div className="panel-head">
                <div>
                  <div className="tiny-label">策略详情</div>
                  <h2>{selected.id}</h2>
                </div>
                <StatusPill tone={pillTone(selected.sourceStatus)}>
                  {statusLabel(selected.sourceStatus)}
                </StatusPill>
              </div>
              <p className="detail-summary">{selected.summary}</p>
              <div className="friendly-stats">
                <div>
                  <span>运行类型</span>
                  <strong>{selected.kind}</strong>
                </div>
                <div>
                  <span>完成时间</span>
                  <strong>{formatDate(selected.createdAt)}</strong>
                </div>
                <div>
                  <span>保存结果</span>
                  <strong>
                    {selected.artifactCount == null
                      ? "已保存"
                      : `${selected.artifactCount} 项`}
                  </strong>
                </div>
                <div>
                  <span>结果复核</span>
                  <strong>{statusLabel(selected.reproduction)}</strong>
                </div>
              </div>
              <div className="result-actions">
                <Link
                  className="button primary"
                  href={`/workflows?mode=backtest&run=${encodeURIComponent(selected.id)}`}
                >
                  再次回测
                </Link>
              </div>
              <details className="run-details">
                <summary>查看技术信息</summary>
                <dl className="evidence-dl">
                  <div>
                    <dt>数据标识</dt>
                    <dd>{selected.dataset}</dd>
                  </div>
                  <div>
                    <dt>运行设置版本</dt>
                    <dd>{selected.protocol}</dd>
                  </div>
                  <div>
                    <dt>结果指纹</dt>
                    <dd>{selected.fingerprint}</dd>
                  </div>
                </dl>
              </details>
            </>
          ) : (
            <div className="empty-state friendly-empty">
              <strong>选择一条记录</strong>
              <p>这里会显示策略的运行摘要和结果信息。</p>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
