import Link from "next/link";
import { AppShell } from "../components/AppShell";
import { RunExplorer } from "./RunExplorer";

export default function RunsPage() {
  return (
    <AppShell
      eyebrow="Results"
      title="策略与回测记录"
      description="查看训练、回测、参数优化和 AI 分析的运行状态。选择一条记录即可查看数据范围和结果摘要。"
      action={
        <Link className="button primary" href="/workflows?mode=backtest">
          新建回测
        </Link>
      }
    >
      <RunExplorer />
    </AppShell>
  );
}
