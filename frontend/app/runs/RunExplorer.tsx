"use client";

import { useMemo, useRef, useState } from "react";
import { StatusPill } from "../components/AppShell";
import { demoRuns, type RunRecord } from "../lib/data";

function normalizeImported(value: unknown): RunRecord[] {
  const candidate =
    typeof value === "object" && value !== null && "runs" in value
      ? (value as { runs: unknown }).runs
      : value;
  if (!Array.isArray(candidate)) throw new Error("JSON 中没有 runs 数组。");
  return candidate.slice(0, 500).map((item, index) => {
    const row =
      typeof item === "object" && item !== null
        ? (item as Record<string, unknown>)
        : {};
    const id = String(row.run_id ?? row.id ?? `imported-run-${index + 1}`);
    const rawStatus = String(row.status ?? "provisional");
    return {
      id,
      kind: String(row.kind ?? row.algorithm ?? "Imported run"),
      status:
        rawStatus === "verified" || rawStatus === "failed"
          ? rawStatus
          : "provisional",
      reproduction: String(
        row.reproduction_level ?? row.reproduction ?? "not_reported",
      ),
      protocol: String(row.protocol ?? row.protocol_id ?? "not_reported"),
      dataset: String(
        row.dataset ?? row.dataset_manifest_hash ?? "not_reported",
      ),
      createdAt: String(row.created_at ?? row.finished_at ?? "imported"),
      summary: String(
        row.summary ??
          "从只读报告 JSON 导入；请在源运行目录核对哈希和审计文件。",
      ),
    };
  });
}

export function RunExplorer() {
  const [runs, setRuns] = useState<RunRecord[]>(demoRuns);
  const [selectedId, setSelectedId] = useState(demoRuns[0].id);
  const [query, setQuery] = useState("");
  const [notice, setNotice] = useState(
    "当前显示内置证据摘要；可导入 cmag report 生成的 JSON。",
  );
  const fileRef = useRef<HTMLInputElement>(null);

  const filtered = useMemo(
    () =>
      runs.filter((run) =>
        `${run.id} ${run.kind} ${run.protocol}`
          .toLowerCase()
          .includes(query.toLowerCase()),
      ),
    [query, runs],
  );
  const selected = runs.find((run) => run.id === selectedId) ?? filtered[0];

  async function importFile(file?: File) {
    if (!file) return;
    try {
      const parsed = JSON.parse(await file.text()) as unknown;
      const imported = normalizeImported(parsed);
      setRuns(imported);
      setSelectedId(imported[0]?.id ?? "");
      setNotice(`已在浏览器内存中导入 ${imported.length} 条记录；未上传文件。`);
    } catch (error) {
      setNotice(
        error instanceof Error ? `导入失败：${error.message}` : "导入失败。",
      );
    }
  }

  return (
    <>
      <section className="toolbar panel">
        <label className="search-field">
          <span className="sr-only">搜索运行</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="按 Run ID、算法或协议搜索…"
          />
        </label>
        <input
          className="sr-only"
          type="file"
          accept=".json,application/json"
          ref={fileRef}
          onChange={(event) => importFile(event.target.files?.[0])}
        />
        <button
          className="button secondary"
          type="button"
          onClick={() => fileRef.current?.click()}
        >
          导入报告 JSON
        </button>
        <button
          className="button ghost"
          type="button"
          onClick={() => {
            setRuns(demoRuns);
            setSelectedId(demoRuns[0].id);
            setNotice("已恢复内置证据摘要。");
          }}
        >
          恢复示例
        </button>
      </section>
      <p className="inline-notice" role="status">
        {notice}
      </p>

      <div className="evidence-layout">
        <section className="panel evidence-list">
          <div className="panel-head">
            <div>
              <div className="tiny-label">Run index</div>
              <h2>{filtered.length} 条记录</h2>
            </div>
          </div>
          <div className="evidence-rows">
            {filtered.map((run) => (
              <button
                type="button"
                className={selected?.id === run.id ? "selected" : undefined}
                onClick={() => setSelectedId(run.id)}
                key={run.id}
              >
                <div>
                  <strong className="mono">{run.id}</strong>
                  <small>{run.kind}</small>
                </div>
                <StatusPill tone={run.status === "verified" ? "good" : "warn"}>
                  {run.status}
                </StatusPill>
              </button>
            ))}
            {filtered.length === 0 && (
              <div className="empty-state">没有匹配的运行。</div>
            )}
          </div>
        </section>

        <section className="panel evidence-detail">
          {selected ? (
            <>
              <div className="panel-head">
                <div>
                  <div className="tiny-label">Selected evidence</div>
                  <h2 className="mono">{selected.id}</h2>
                </div>
                <StatusPill
                  tone={selected.status === "verified" ? "good" : "warn"}
                >
                  {selected.status}
                </StatusPill>
              </div>

              <p className="detail-summary">{selected.summary}</p>
              <dl className="evidence-dl">
                <div>
                  <dt>复现等级</dt>
                  <dd>{selected.reproduction}</dd>
                </div>
                <div>
                  <dt>协议</dt>
                  <dd>{selected.protocol}</dd>
                </div>
                <div>
                  <dt>数据清单</dt>
                  <dd>{selected.dataset}</dd>
                </div>
                <div>
                  <dt>时间 / 阶段</dt>
                  <dd>{selected.createdAt}</dd>
                </div>
              </dl>

              <div className="integrity-box">
                <div>
                  <span className="integrity-mark">✓</span>
                  <div>
                    <strong>证据查看边界</strong>
                    <p>
                      此页面仅显示公开摘要。完整性结论应以源目录中的
                      run_manifest、SHA-256 与 reproduction_comparison 为准。
                    </p>
                  </div>
                </div>
                <code>cmag verify --run-id {selected.id}</code>
              </div>
            </>
          ) : (
            <div className="empty-state">选择一条运行以查看证据。</div>
          )}
        </section>
      </div>
    </>
  );
}
