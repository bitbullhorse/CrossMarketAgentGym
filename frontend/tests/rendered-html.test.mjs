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

test("server-renders the consumer strategy experience and all primary routes", async () => {
  const cases = [
    ["/", "不写代码，也能训练和回测"],
    ["/workflows", "创建并测试你的策略"],
    ["/runs", "策略与回测记录"],
    ["/experiments", "选择策略方法的参考"],
    ["/settings", "应用设置"],
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

test("keeps user-facing safety boundaries visible without development workflow copy", async () => {
  const [home, workflows, experiments, workflowSource] = await Promise.all([
    render("/").then((response) => response.text()),
    render("/workflows").then((response) => response.text()),
    render("/experiments").then((response) => response.text()),
    readFile(new URL("../app/workflows/WorkflowBuilder.tsx", import.meta.url), "utf8"),
  ]);

  assert.match(home, /不会连接或修改真实账户/);
  assert.match(home, /训练调参不会偷看最终测试数据/);
  assert.match(workflows, /AI 也不能绕过/);
  assert.match(workflowSource, /最终区间不是日常调参工具/);
  assert.match(experiments, /历史表现不代表未来收益/);
  assert.doesNotMatch(home, /Phase \d+|冻结协议|独立复核|开发流程/);
  assert.doesNotMatch(workflows, /Phase \d+|冻结协议|独立复核|开发流程/);
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
  assert.match(combined, /不保存任何密钥/);
});
