# CrossMarketAgentGym GUI

面向研究者的只读控制台，用于生成受控 CLI 命令、浏览运行证据、审阅
Phase 12 冻结协议结果和配置本地报告服务。

安全边界：

- 不在浏览器中接收、显示或持久化 API Key、SSH 或 GitHub 凭据；
- 不直接执行训练或修改账户状态；
- HPO 命令只面向训练/验证分区；
- 测试分区需要显式确认；
- Phase 12 独立复核完成前，结果始终标记为 provisional。

## 本地运行

```bash
pnpm install
pnpm dev
```

生产验证：

```bash
pnpm lint
pnpm exec tsc --noEmit
pnpm test
```
