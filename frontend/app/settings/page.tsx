import { AppShell, StatusPill } from "../components/AppShell";
import { SettingsPanel } from "./SettingsPanel";

export default function SettingsPage() {
  return (
    <AppShell
      eyebrow="Local preferences"
      title="连接设置"
      description="配置只读报告服务与界面偏好。所有设置只保存在当前浏览器；凭据和模型密钥始终由后端环境管理。"
      action={<StatusPill tone="good">no secrets</StatusPill>}
    >
      <SettingsPanel />
    </AppShell>
  );
}
