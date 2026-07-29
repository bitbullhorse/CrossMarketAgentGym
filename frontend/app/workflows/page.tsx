import { AppShell, StatusPill } from "../components/AppShell";
import { WorkflowBuilder } from "./WorkflowBuilder";

export default function WorkflowsPage() {
  return (
    <AppShell
      eyebrow="Guarded orchestration"
      title="工作流编排"
      description="选择确定性配置，再生成可审计的 CLI 命令。GUI 不直接执行训练，也不会把密钥或账户写入浏览器。"
      action={<StatusPill tone="good">safe command mode</StatusPill>}
    >
      <WorkflowBuilder />
    </AppShell>
  );
}
