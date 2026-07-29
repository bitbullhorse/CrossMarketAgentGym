import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const workerUrl = new URL("../dist/server/index.js", import.meta.url);
workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
const { default: worker } = await import(workerUrl.href);

async function render(path = "/") {
  return worker.fetch(
    new Request(`http://localhost${path}`, {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the control center and all primary routes", async () => {
  const cases = [
    ["/", "让每次实验都有边界"],
    ["/workflows", "工作流编排"],
    ["/runs", "运行证据"],
    ["/experiments", "Phase 12 正式实验"],
    ["/settings", "连接设置"],
  ];

  for (const [path, expected] of cases) {
    const response = await render(path);
    assert.equal(response.status, 200, path);
    assert.match(
      response.headers.get("content-type") ?? "",
      /^text\/html\b/i,
      path,
    );
    const html = await response.text();
    assert.match(html, new RegExp(expected), path);
    assert.match(html, /CrossMarketAgentGym/, path);
    assert.doesNotMatch(html, /codex-preview|Your site is taking shape/i, path);
  }
});

test("keeps the safety and frozen-protocol disclosures visible", async () => {
  const [home, workflows, experiments] = await Promise.all([
    render("/").then((response) => response.text()),
    render("/workflows").then((response) => response.text()),
    render("/experiments").then((response) => response.text()),
  ]);

  assert.match(home, /INDEPENDENT_REVIEW_MISSING/);
  assert.match(home, /不会直接修改账户/);
  assert.match(workflows, /测试集不对 HPO 可见/);
  assert.match(workflows, /风险层不可绕过/);
  assert.match(experiments, /0 \/ 200/);
  assert.match(experiments, /不得作为最终论文结论/);
});

test("does not embed credentials in source or rendered HTML", async () => {
  const sources = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/settings/SettingsPanel.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/workflows/WorkflowBuilder.tsx", import.meta.url), "utf8"),
  ]);
  const html = await render("/settings").then((response) => response.text());
  const combined = `${sources.join("\n")}\n${html}`;

  assert.doesNotMatch(combined, /\bsk-[a-zA-Z0-9]{12,}\b/);
  assert.doesNotMatch(combined, /https?:\/\/[^/\s]+:[^@\s]+@/);
  assert.match(combined, /浏览器中没有密钥/);
});
