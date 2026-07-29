# CrossMarketAgentGym GUI

面向普通策略用户的图形化智能策略实验室。用户可以通过向导选择数据、算法、
训练强度和风险偏好，并启动策略训练、历史回测、参数优化或 AI 顾问分析。
常用操作不要求编写 YAML 或命令行；高级配置默认折叠。

安全边界：

- 不在浏览器中接收、显示或持久化 API Key、SSH 或 GitHub 凭据；
- 只能通过 loopback FastAPI 提交白名单任务，不能执行任意命令；
- 日常回测写入独立目录，最终留出区间需要显式确认；
- 参数优化只使用训练和验证数据；
- LLM 仍不能直接修改账户状态或绕过确定性风险层；
- 工程门禁、复现信息和底层命令不会出现在普通用户的主要操作流程中。

## 本地运行

先在仓库根目录启动后端：

```bash
cmag service run --config configs/reporting/gui.yaml
```

前端要求 Node.js `>=22.13.0` 和 pnpm `11.9.0`。Windows 首次运行：

```powershell
winget install --id OpenJS.NodeJS.LTS -e
npm install --global pnpm@11.9.0 --registry=https://registry.npmmirror.com
```

重新打开 PowerShell，进入 `frontend` 后启动：

```bash
pnpm install --registry=https://registry.npmmirror.com
pnpm dev
```

GUI 地址是 `http://localhost:3000`；`http://127.0.0.1:8000/health` 是后端健康
接口。不要使用不带端口的 `http://localhost`。GUI 默认连接
`http://127.0.0.1:8000`，可在“连接设置”中修改；浏览器只保存服务 URL。
详细说明见 [`docs/gui.zh-CN.md`](../docs/gui.zh-CN.md)。

生产验证：

```bash
pnpm lint
pnpm exec tsc --noEmit
pnpm test
```
