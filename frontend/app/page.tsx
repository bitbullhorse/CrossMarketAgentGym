import Link from "next/link";
import { AppShell, StatusPill } from "./components/AppShell";

const starterCards = [
  {
    title: "快速体验",
    tag: "约 1 分钟",
    copy: "使用内置跨市场样本和推荐参数，完成第一次策略训练。",
    href: "/workflows?mode=train",
    action: "开始体验",
  },
  {
    title: "训练我的策略",
    tag: "可自定义",
    copy: "选择算法、训练强度和风险偏好，系统自动生成可运行配置。",
    href: "/workflows?mode=train",
    action: "创建策略",
  },
  {
    title: "回测已有策略",
    tag: "历史模拟",
    copy: "输入已有策略名称，在验证区间查看收益、回撤和交易表现。",
    href: "/workflows?mode=backtest",
    action: "运行回测",
  },
];

export default function Home() {
  return (
    <AppShell
      eyebrow="Cross-market strategy studio"
      title="不写代码，也能训练和回测智能交易策略"
      description="从数据、算法到风险控制，跟随向导完成配置。所有交易只发生在模拟环境，不会连接或修改真实账户。"
      action={
        <Link className="button primary" href="/workflows">
          创建新策略 <span aria-hidden="true">→</span>
        </Link>
      }
    >
      <section className="consumer-hero panel">
        <div className="hero-copy">
          <StatusPill tone="good">本地数据 · 模拟交易</StatusPill>
          <h2>用四步完成你的第一套跨市场策略</h2>
          <p>
            选择数据和算法，设定能承受的风险，启动训练，再用历史行情检验表现。
            复杂配置由系统自动完成，高级用户仍可展开详细设置。
          </p>
          <div className="hero-actions">
            <Link className="button primary" href="/workflows?mode=train">
              开始创建
            </Link>
            <Link className="button secondary" href="/runs">
              查看已有结果
            </Link>
          </div>
        </div>
        <div className="journey-card" aria-label="策略创建步骤">
          {[
            ["1", "选择数据", "确定用于训练的市场数据"],
            ["2", "设计策略", "选择算法与训练强度"],
            ["3", "控制风险", "设置仓位、现金和换手限制"],
            ["4", "训练回测", "查看策略在历史行情中的表现"],
          ].map(([number, label, note]) => (
            <div className="journey-step" key={number}>
              <span>{number}</span>
              <div>
                <strong>{label}</strong>
                <small>{note}</small>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="starter-grid" aria-label="常用入口">
        {starterCards.map((card) => (
          <Link className="starter-card panel" href={card.href} key={card.title}>
            <span>{card.tag}</span>
            <h2>{card.title}</h2>
            <p>{card.copy}</p>
            <strong>{card.action} →</strong>
          </Link>
        ))}
      </section>

      <section className="panel protection-strip">
        <div>
          <div className="tiny-label">自动保护</div>
          <h2>你专注策略想法，系统负责守住边界</h2>
        </div>
        <ul>
          <li>训练调参不会偷看最终测试数据</li>
          <li>AI 建议必须通过仓位与现金限制</li>
          <li>交易成本和滑点会计入回测</li>
          <li>每次运行都保留配置和结果</li>
        </ul>
      </section>
    </AppShell>
  );
}
