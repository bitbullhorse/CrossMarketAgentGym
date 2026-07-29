import { AppShell } from "../components/AppShell";
import { WorkflowBuilder } from "./WorkflowBuilder";

export default function WorkflowsPage() {
  return (
    <AppShell
      eyebrow="Strategy builder"
      title="创建并测试你的策略"
      description="选择你想做的事情，按页面提示填写常用参数。系统会自动检查配置并在后台启动任务。"
    >
      <WorkflowBuilder />
    </AppShell>
  );
}
