import { AppShell } from "../components/AppShell";
import { SettingsPanel } from "./SettingsPanel";

export default function SettingsPage() {
  return (
    <AppShell
      eyebrow="Preferences"
      title="应用设置"
      description="检查本地策略服务、AI 顾问和训练环境是否可用。你的密钥和数据不会保存在网页中。"
    >
      <SettingsPanel />
    </AppShell>
  );
}
