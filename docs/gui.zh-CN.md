# CrossMarketAgentGym GUI 操作指南

GUI 是本地研究控制台。它通过受控 FastAPI 服务调用现有的 `cmag` 工作流，可编辑并
校验 YAML、启动数据检查、环境检查、训练、验证集回测、锁定测试评估、Agent、HPO、
计算重放、报告和冻结实验任务，也可查看任务状态、实时日志和运行证据。

GUI 不改变项目的安全边界：

- 浏览器不能提交任意命令，只能选择后端白名单中的任务类型；
- 配置必须位于对应的 `configs/` 子目录，并通过当前 Pydantic 模型校验；
- DeepSeek Key 只由后端进程环境变量读取，不进入浏览器、YAML、URL 或任务日志；
- HPO 请求没有测试分区字段；
- validation 回测写入独立目录，不覆盖源训练运行；
- test 是一次性锁定评估，必须显式确认，也不能在运行中取消；
- LLM 仍只生成结构化指令，账户状态只能由环境和确定性风险投影层更新；
- Phase 12 正式任务只有在当前 Git commit 与冻结 matrix 绑定 commit 一致时才可执行。

## 1. 安装

在仓库根目录安装 Python 后端。清华 PyPI 镜像可提高依赖下载稳定性：

```bash
export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
python -m pip install -c constraints-cpu.txt -e ".[all,service]"
```

Windows PowerShell：

```powershell
$env:PIP_INDEX_URL = "https://pypi.tuna.tsinghua.edu.cn/simple"
python -m pip install -c constraints-cpu.txt -e ".[all,service]"
```

前端要求 Node.js `>=22.13.0` 和 pnpm `11.9.0`。Windows 可先安装 Node.js，
关闭并重新打开 PowerShell，再通过 npm 安装固定版本的 pnpm：

```powershell
winget install --id OpenJS.NodeJS.LTS -e
npm install --global pnpm@11.9.0 --registry=https://registry.npmmirror.com
node --version
pnpm --version
```

然后安装前端依赖：

```bash
cd frontend
pnpm install --registry=https://registry.npmmirror.com
```

## 2. 启动

终端一：从仓库根目录启动本地控制服务：

```bash
cmag service run --config configs/reporting/gui.yaml
```

终端二：启动前端：

```bash
cd frontend
pnpm dev
```

打开 `http://localhost:3000`，不要只打开不带端口的 `http://localhost`。
在“连接设置”中使用默认后端地址
`http://127.0.0.1:8000`，点击“探测服务”。健康检查应显示
`execution_enabled: true`。

可先直接检查后端：

```text
http://127.0.0.1:8000/health
```

端口职责如下：

- `3000`：GUI 页面；
- `8000`：后端 API；根路径没有页面，健康接口是 `/health`。

`configs/reporting/service.yaml` 保持只读；只有
`configs/reporting/gui.yaml` 显式设置 `execution_enabled: true`。执行服务强制绑定
loopback，不能通过 `allow_remote` 暴露到局域网。

## 3. 配置与启动工作流

进入“工作流”页：

1. 选择数据验证、环境检查、训练、Agent、HPO 或报告；
2. 从白名单中选择一个现有 YAML 模板；
3. 在编辑器中修改字段；
4. 点击“验证配置”；只有严格 Schema 和安全检查通过后才可提交；
5. 点击“启动任务”，页面会显示 job ID、状态和日志；
6. 普通任务可取消；锁定测试和正式实验开始后不能中断。

训练算法由训练 YAML 的 `trainer.algorithm` 控制，支持 PPO、SAC、TD3 和 A2C。PPO、
SAC、TD3 是 Phase 12 冻结 Benchmark 方法；A2C 仅作为开发实验。

AgentRuntime 的 YAML 可配置 Agent 类型、数量、工具、`deepseek-v4-pro` 模型、通信
拓扑、最大轮数、quorum 和冲突裁决策略。三层 Agent 使用带 `preset` 的 Phase 7
配置；Research、Risk 和 Hierarchical 三层可独立开关，但仍共享统一运行时与确定性
风险边界。

HPO 的 `searcher` 与 `scheduler` 是两个独立配置块。九种搜索算法均可选择；ASHA、
HyperBand 和 PBT 只负责资源调度。HPO 配置不存在测试集选择入口。

## 4. 回测和锁定测试

“回测”默认选择 `validation`：

- 读取已训练 run 的 checkpoint；
- 重新创建相同验证环境；
- 把 Metrics、Trades、Weights 和来源记录写入
  `runs/backtests/<gui-job-id>/`；
- 不覆盖源 run，也没有模型选择之外的测试权限。

选择 `test` 会触发一次性锁定测试评估。必须勾选确认；如果源 run 已存在
`test/metrics.json`，后端拒绝再次执行。锁定测试开始后不能从 GUI 中断。

## 5. 任务、日志与产物

任务控制记录位于：

```text
logs/gui-jobs/<job-id>/
├── config.resolved.yaml
├── job.json
└── output.log
```

训练、Agent、HPO、重放和报告仍写入各自原有的 `runs/`、`results/`、`reports/`
目录。任务日志只是运行输出；研究结论仍应以 run manifest、数据 hash、checkpoint、
metrics 和审计文件为准。

## 6. DeepSeek

在线 Agent 运行前，在启动后端的同一终端设置：

```bash
export DEEPSEEK_API_KEY="<通过安全渠道提供>"
export DEEPSEEK_BASE_URL="https://api.deepseek.com"
cmag service run --config configs/reporting/gui.yaml
```

GUI 只显示 Key 是否已配置，不返回 Key 值。所有在线 Agent 的模型固定为
`deepseek-v4-pro`。

## 7. 远程 GPU

远程主机上的 GUI 后端仍应只监听 `127.0.0.1`。通过 SSH 端口转发访问：

```bash
ssh -L 8000:127.0.0.1:8000 <user>@<host>
```

然后在远程仓库中使用 GPU Python 环境启动服务，在本机 GUI 中连接
`http://127.0.0.1:8000`。不要把执行 API 直接暴露到公网或局域网。

## 8. 常见问题

- “localhost 拒绝连接”：确认地址包含 `:3000`，并保持执行 `pnpm dev` 的第二个
  PowerShell 窗口处于运行状态；用 `http://127.0.0.1:8000/health` 单独验证后端。
- “无法识别 pnpm”：本机尚未安装 Node.js/pnpm，按第 1 节安装后关闭并重新打开
  PowerShell。若 `node --version` 也失败，说明 Node.js 尚未加入当前终端的 `PATH`。
- “配置不存在”：只能选择对应 `configs/data`、`configs/env`、`configs/train`、
  `configs/agents`、`configs/tune` 和 `configs/reporting` 下的 YAML。
- “服务只读”：启动的是 `service.yaml`；请改用 `gui.yaml`。
- “正式实验 commit gate 未通过”：当前 checkout 与冻结 matrix 不一致。不要修改旧
  matrix；切换到绑定 commit，或为新增实验创建新协议和新 matrix 修订版。
- “任务已有产物”：运行证据不可覆盖。修改 run/study/report ID 后重新提交。
- “无法连接 DeepSeek”：在后端进程环境中检查 `DEEPSEEK_API_KEY`，不要把 Key 复制
  到 YAML 或浏览器。
