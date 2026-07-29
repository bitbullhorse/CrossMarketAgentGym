import { AppShell, StatusPill } from "../components/AppShell";
import { RunExplorer } from "./RunExplorer";

export default function RunsPage() {
  return (
    <AppShell
      eyebrow="Evidence ledger"
      title="运行证据"
      description="浏览公开的运行索引、导入本地 JSON，并核对复现等级。原始提示词、配置和 Checkpoint 不会上传到托管界面。"
      action={<StatusPill tone="neutral">read-only</StatusPill>}
    >
      <RunExplorer />
    </AppShell>
  );
}
