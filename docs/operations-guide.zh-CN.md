# CrossMarketAgentGym 详细操作手册

本文档面向安装人员、研究人员、算法工程师、复核人员和发布维护者，覆盖从 CPU
快速验证到数据接入、强化学习训练、三层 LLM Agent、超参数优化、计算复现、报告、
Docker、Ray/GPU 和审计的完整操作路径。

当前软件候选版本为 `v1.0.0-rc2`。它不是正式的 `v1.0.0`，内置五日合成数据仅用于
兼容性与复现验证，不能作为论文结果、投资业绩或生产交易依据。

## 1. 使用前必须了解的边界

CrossMarketAgentGym 是研究与回测平台，不是实盘下单系统。以下规则在所有工作流中
都不可绕过：

1. 收盘后时点 `t` 形成的信号，最早在下一可交易日开盘 `t+1` 执行。
2. 训练和 HPO 只能读取训练集与验证集；测试集只允许在配置锁定后执行一次。
3. LLM 只能产生经过 Schema 校验的建议或约束，不能直接调用环境 `step`、修改现金、
   持仓或账户净值。
4. 管理员风险约束位于 LLM 下游；Agent 只能收紧约束，不能放宽或绕过约束。
5. 搜索算法、资源调度器和执行后端是三个独立组件。ASHA、HyperBand、PBT 不是搜索
   算法。
6. 数据 Manifest、配置、Checkpoint 和运行产物使用哈希绑定。不要覆盖或手工修补
   已有运行目录。
7. 任何信息泄漏、会计错误、安全缺陷或复现失败都应视为阻断问题。
8. API 密钥只能通过进程环境变量提供，禁止写入 YAML、代码、命令参数、测试、日志
   或报告。

建议始终在仓库根目录执行本手册中的命令。相对数据路径、输出路径和运行目录通常
相对于当前工作目录解析；HPO 的 `objective.base_train_config` 相对于 HPO 配置文件
所在目录解析。

## 2. 软件组成

主要目录如下：

```text
CrossMarketAgentGym/
├── configs/                 # 数据、环境、训练、Agent、HPO、报告配置
├── data/sample/             # 随包发布的四市场合成数据
├── stock_data/              # 本地原始 OHLCV；被 Git 和发行包排除
├── src/crossmarket_agentgym/
│   ├── data/                # 数据 Schema、Manifest、质量验证与旧格式适配
│   ├── environments/        # Gymnasium 环境、约束投影、执行和会计
│   ├── rl/                  # PPO、SAC、TD3、A2C 训练与锁定测试
│   ├── agents/              # Provider、工具、统一 AgentRuntime、三层 Agent
│   ├── tuning/              # 搜索器、调度器、Study 与 Local/Ray 执行
│   ├── reporting/           # 只读运行索引和 SoftwareX 报告
│   ├── api/                 # 可选只读 FastAPI 服务
│   └── release/             # quickstart、复现和发行检查
├── runs/                    # 本地运行证据；被 Git 排除
├── reports/                 # 本地报告；被 Git 排除
├── experiments/             # 冻结实验协议、矩阵和 Prompt 版本
├── tests/                   # 单元、集成、泄漏、安全与复现测试
├── Dockerfile
├── environment-cpu.yml
├── environment-gpu.yml
├── constraints-cpu.txt
└── constraints-gpu.txt
```

命令行入口为 `cmag`：

```bash
cmag --version
cmag --help
```

## 3. 安装

### 3.1 基础要求

- 操作系统：Windows、Linux 或 macOS；正式 CPU/Docker 证据使用 Ubuntu 24.04。
- Python：3.11 或 3.12。
- 内存：快速验证建议至少 4 GB；Docker 复现配置为 7 GB。
- 磁盘：基础源码和 CPU quickstart 只需少量空间；正式训练、Checkpoint 和 Ray
  实验应预留独立的大容量目录。
- GPU：可选。CPU 是参考执行路径。

### 3.2 配置清华源

Linux/macOS：

```bash
export PIP_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"
```

PowerShell：

```powershell
$env:PIP_INDEX_URL = "https://pypi.tuna.tsinghua.edu.cn/simple"
```

如果希望持久配置，请使用本机的 pip 配置机制；不要将个人镜像凭据写入仓库。

### 3.3 使用 venv 安装 CPU 开发环境

Linux/macOS：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -c constraints-cpu.txt \
  -e ".[dev,legacy-data,release,service]"
```

PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -c constraints-cpu.txt `
  -e ".[dev,legacy-data,release,service]"
```

验证安装：

```bash
cmag --version
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

CPU 环境中第二个值应为 `False`。

### 3.4 使用 Conda 安装

CPU：

```bash
conda env create -f environment-cpu.yml
conda activate crossmarket-agent-gym-cpu
cmag --version
```

GPU：

```bash
conda env create -f environment-gpu.yml
conda activate crossmarket-agent-gym-gpu
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

GPU 环境固定了 PyTorch 2.7.1 与 CUDA 12.6 运行时约束。实际使用前仍须确认主机
NVIDIA 驱动与 PyTorch CUDA 构建兼容。

### 3.5 从 wheel 安装

维护者先构建：

```bash
python -m pip install "build>=1.2,<2"
python -m build --wheel
```

在一个全新虚拟环境中安装：

```bash
python -m pip install -c constraints-cpu.txt \
  "dist/crossmarket_agent_gym-1.0.0rc2-py3-none-any.whl[rl,hpo,llm]"
cmag quickstart --smoke-steps 64
```

发布 wheel 已包含示例配置、合成数据、Mock/Replay 资源、发行资源和冻结 Schema。

### 3.6 可选依赖

| Extra | 用途 |
|---|---|
| `legacy-data` | 读取旧 CSV、XLS、XLSX 数据 |
| `rl` | Stable-Baselines3 与 PyTorch |
| `hpo` | Optuna、SciPy 相关 HPO 能力 |
| `llm` | OpenAI-compatible HTTP Provider |
| `ray` | Ray Trial 并行执行 |
| `service` | FastAPI/Uvicorn 只读报告服务 |
| `release` | 构建与 Twine 检查 |
| `dev` | 测试、覆盖率、Ruff、mypy 等开发工具 |
| `all` | 全部运行时可选能力，不含开发工具 |

按需安装，例如：

```bash
python -m pip install -e ".[rl,hpo,llm]"
```

## 4. 十分钟 CPU 快速验证

首先运行不训练、不联网的打包 quickstart：

```bash
cmag quickstart --smoke-steps 64
```

它只验证随包数据、Manifest、环境、随机动作、有限值和会计恒等式，不会下载数据、
调用 LLM、训练模型、调参、访问测试集或修改外部账户。

完整 Phase 11 风格的本地 CPU 路径为：

```bash
cmag data validate --config configs/data/sample.yaml
cmag env check --config configs/env/sample_cross_market.yaml
cmag train --config configs/train/ppo_quickstart.yaml
cmag agent run --config configs/agents/research_single_mock.yaml
cmag agent run --config configs/agents/risk_committee_mock.yaml
cmag tune --config configs/tune/ppo_pso_quickstart.yaml
cmag report --run-id repro-ppo-quickstart
cmag reproduce --run-id repro-ppo-quickstart --verify-only
cmag reproduce \
  --run-id repro-ppo-quickstart \
  --execute \
  --compare \
  --tolerance-config configs/reproduction/phase11_cpu.yaml
```

若 `repro-ppo-quickstart` 已存在，训练命令会拒绝覆盖。请复制配置并修改
`run_name`，或在新的 `--workspace-root`/工作目录中执行；不要删除原目录来“解决”
冲突。

## 5. 数据操作

### 5.1 数据模式

系统支持两种入口：

- `canonical_manifest`：推荐。Parquet 数据由 `dataset_manifest.json` 绑定；
- `legacy_mixed`：兼容本地 Yahoo 风格 CSV 与 RESSET Excel，仅进行只读检查和适配。

随包样例：

```yaml
dataset:
  root: data/sample
  layout: canonical_manifest
```

本地 `stock_data` 示例：

```yaml
dataset:
  root: stock_data
  layout: legacy_mixed
  markets:
    A股: CN
    港股: HK
    日股: JP
    美股: US
  mutation_policy: reject
```

### 5.2 验证数据

验证合成 canonical 数据：

```bash
cmag data validate --config configs/data/sample.yaml
```

快速抽查旧格式数据：

```bash
cmag data validate \
  --config configs/data/local_stock_data.yaml \
  --max-files-per-market 5
```

完整检查旧格式数据：

```bash
cmag data validate --config configs/data/local_stock_data_full.yaml
```

`--max-files-per-market` 只限制旧格式检查数量，对 canonical Manifest 无效。验证过程
不会删除、排序、填补、修正或覆写 `stock_data/`。

### 5.3 Canonical OHLCV 要求

主键为 `(trade_date, symbol, market)`。必需字段：

```text
trade_date, symbol, market, exchange,
open, high, low, close, volume,
currency, timezone, adjusted, source
```

可选字段：

```text
adjusted_close, turnover, suspension_flag,
limit_up, limit_down, tradable
```

关键质量规则：

- OHLCV 必须有限且非负；
- `high` 不低于 open/close，`low` 不高于 open/close；
- 同一市场和证券的日期不得倒序，主键不得重复；
- 市场、币种和时区必须一致；
- Manifest 中每个文件的相对路径、字节数、行数、日期范围与 SHA-256 必须匹配；
- 缺失数据不能通过静默前向填充变成“可交易”数据；
- 价格前向填充只可用于估值，停牌或无观测时 `tradable=false`。

市场元数据：

| 市场 | 币种 | 时区 |
|---|---|---|
| CN | CNY | Asia/Shanghai |
| HK | HKD | Asia/Hong_Kong |
| JP | JPY | Asia/Tokyo |
| US | USD | America/New_York |

Manifest 哈希不一致时，应把数据视为已变更或损坏，创建新的版本化数据快照；禁止直接
编辑 Manifest 来消除错误。

## 6. 环境检查与交易语义

### 6.1 执行环境检查

```bash
cmag env check --config configs/env/sample_cross_market.yaml
```

检查内容包括：

- Gymnasium API；
- 安装 SB3 后的 SB3 环境检查；
- 随机种子和随机动作 smoke test；
- 观察、动作、奖励和账户数值有限性；
- 每一步现金、持仓、费用、滑点和净值的会计核对；
- `market_window` 布局与特征提取器兼容性。

验收时应确认 `is_valid=true`、Gymnasium 通过、SB3 通过或明确显示未安装，并且最大
会计误差不超过配置中的 `accounting_tolerance`，默认上限为 `1e-8`。

### 6.2 关键环境配置

```yaml
observation:
  market_window_layout: flat

environment:
  execution_protocol: close_signal_next_open
  base_currency: USD
  lookback: 20
  initial_cash: 1000000
  allow_short: false
  max_leverage: 1.0
  max_asset_weight: 0.10
  max_market_weight: 0.40
  market_weight_overrides: {}
  cash_floor: 0.05
  max_turnover: 1.0
  transaction_cost_bps: 10
  slippage_bps: 5
  reward: risk_adjusted
  risk_aversion: 0.10
  drawdown_penalty: 0.50
  cvar_alpha: 0.05
  cvar_penalty: 0.50
  lot_sizes: {}
  t_plus_one_markets: [CN]
  max_episode_steps: null
  accounting_tolerance: 1.0e-8
```

奖励类型可选：

```text
log_return
return_minus_cost
risk_adjusted
differential_sharpe
drawdown_penalty
cvar_penalty
```

### 6.3 观察布局

`flat`：

- 将内部 `[N,L,F]` 市场窗口按 C 顺序展开为一维；
- OHLCV 仍是 `float32`，不会转为 `uint8` 或缩放到 `[0,255]`；
- 是 PPO、SAC、TD3 的默认 SB3 快速路径；
- 配合 `trainer.policy: mlp`。

`tensor`：

- 对外保留 `[N,L,F]`；
- 适用于 Transformer、共享资产编码器、IR-MoE 或自定义特征提取器；
- SB3 运行必须显式使用自定义 `BaseFeaturesExtractor`；
- 配合 `trainer.policy: shared_mlp` 或 `transformer`。

不要为了消除 SB3 图像启发式警告而改变 OHLCV 的数据类型或数据语义。

### 6.4 动作与会计

动作形状为 `[N+1]`，现金权重在首位。处理顺序是：

```text
原始动作
→ 清理 NaN/Inf
→ 多头或带符号归一化
→ 冻结不可交易持仓
→ 资产/市场/杠杆/现金约束
→ 换手率约束
→ 手数、T+1、停牌、涨跌停和现金执行规则
→ ExecutionEngine 原子替换账户状态
```

每一步审计会记录原始、归一化和投影动作，裁剪原因、未解决约束、成交数量、拒单原因、
成交额、费用、滑点、换手、净值、回撤、市场敞口和会计误差。

## 7. 强化学习训练与锁定测试

### 7.1 支持的算法和策略

算法：

```text
PPO, SAC, TD3, A2C
```

策略：

| 策略 | 观察布局 | 用途 |
|---|---|---|
| `mlp` | `flat` | 默认 CPU/SB3 路径 |
| `shared_mlp` | `tensor` | 共享资产编码和跨资产池化 |
| `transformer` | `tensor` | 资产—时间注意力 |

### 7.2 训练配置结构

以 `configs/train/ppo_quickstart.yaml` 为基础复制新文件，并至少修改 `run_name`：

```yaml
dataset_root: data/sample
output_dir: runs
run_name: my-ppo-run-001

observation:
  market_window_layout: flat

environment:
  execution_protocol: close_signal_next_open
  lookback: 1
  accounting_tolerance: 1.0e-8

split:
  train_end_execution_index: 2
  validation_end_execution_index: 3
  test_end_execution_index: 4

trainer:
  algorithm: PPO
  policy: mlp
  total_timesteps: 16
  learning_rate: 0.0003
  gamma: 0.99
  n_steps: 4
  batch_size: 2
  n_epochs: 1
  device: cpu
  seed: 1024
  deterministic_eval: true
  eval_episodes: 1

callbacks:
  checkpoint_freq: 0
  validation_freq: 0
  early_stop_patience: 0
  finite_guard: true
  max_drawdown: 0.80
  resource_monitor_freq: 0
  audit_freq: 0
  metrics_freq: 0
```

PPO 必须满足 `batch_size <= n_steps`；SAC/TD3 必须满足
`batch_size <= buffer_size`；Transformer 的 `model_dim` 必须能被 `heads` 整除。

### 7.3 训练

```bash
cmag train --config configs/train/ppo_quickstart.yaml
```

其他示例：

```bash
cmag train --config configs/train/sac.yaml
cmag train --config configs/train/td3.yaml
```

训练过程只构造 `train` 和 `validation` 能力，不构造测试环境。验证可用于早停，但测试
指标不会暴露给回调。

### 7.4 运行产物

典型目录：

```text
runs/<run_id>/
├── resolved_config.json
├── training_artifact.json
├── run_summary.json
├── run_manifest.json
├── checkpoints/
│   ├── final_model.zip
│   └── step_*_steps.zip
└── validation/
    ├── metrics.json
    ├── trades.json
    └── weights.json
```

启用相应 callback 时还会产生 `audit.jsonl`、`resources.jsonl`、
`training_metrics.jsonl`、`validation.jsonl` 和周期 Checkpoint。Agent 与计算重放
目录还会保存 `config.resolved.yaml`。`run_manifest.json` 是权威产物索引，记录
配置、数据、协议、代码、种子、运行时和产物哈希。

`run_summary.json` 包含：

```text
started_at, finished_at, runtime_seconds,
training_runtime_seconds, evaluation_runtime_seconds,
device, torch_version, python_version, cpu_model, gpu_model
```

验证指标还会记录 `evaluation_episodes`、样本数和 `statistical_warnings`。只有一个
episode 时，即使 `std_return=0.0`，也不应将其解读为可靠的离散程度。

### 7.5 锁定测试

完成训练、HPO 和配置锁定之后，才运行：

```bash
cmag evaluate --run-id my-ppo-run-001
```

也可以传入运行目录：

```bash
cmag evaluate --run-id runs/my-ppo-run-001
```

命令加载最终 Checkpoint，只构造 `test` 分区，并写入 `test/`。同一运行的第二次测试
评估会被拒绝，避免覆盖和重复窥视。不得根据测试结果返回修改超参数或选择模型。

## 8. 统一 AgentRuntime

### 8.1 Provider

所有单 Agent 和多 Agent 都通过同一个 `AgentRuntime`。Provider 可选：

```text
openai_compatible
mock
replay
```

所有 Agent 的模型名必须为：

```text
deepseek-v4-pro
```

`mock` 用于离线确定性测试；`replay` 只接受与原请求规范化哈希一致的记录；
`openai_compatible` 用于在线 DeepSeek API。

### 8.2 离线单 Agent

```bash
cmag agent run --config configs/agents/runtime_single_offline.yaml
```

该示例使用 Research Coordinator、Mock Provider 和只读 `inspect_dataset` 工具，不需要
网络或密钥。

### 8.3 离线多 Agent

```bash
cmag agent run --config configs/agents/runtime_team_offline.yaml
```

示例展开一个研究协调者、三个风险管理者和两个审计者，并故意制造一个 Provider
失败，以验证静态安全回退、quorum 和最保守聚合。

### 8.4 通信拓扑

`team.topology` 支持：

| 值 | 语义 |
|---|---|
| `single` | 恰好一个启用的 Agent 实例 |
| `pipeline` | 按配置顺序串行传递结构化结果 |
| `supervisor_worker` | 一个 supervisor 协调多个 worker |
| `committee_vote` | 委员会并行或串行投票 |
| `debate_then_judge` | 多方辩论后由单一 judge 裁决 |
| `map_reduce` | worker 分治，supervisor 汇总 |

冲突策略：

```text
weighted_vote
majority_vote
judge
most_conservative
reject
```

配置示例：

```yaml
team:
  topology: committee_vote
  max_rounds: 3
  quorum: 0.5
  conflict_policy: most_conservative
  parallel: true
  max_workers: 6
  agents:
    - type: risk_manager
      name: risk_committee
      count: 3
      provider: mock
      model: deepseek-v4-pro
      tools: []
```

单个 `AgentSpec` 可配置：

```text
type, name, count, enabled,
provider, model, prompt_template,
tools, allowed_permissions,
weight, temperature, max_tokens,
timeout_seconds, max_retries, retry_backoff_seconds,
max_tool_rounds, max_tool_calls, max_expensive_tool_calls,
max_tool_seconds, require_budget_before_expensive,
api_key_env, base_url_env, endpoint,
structured_output_mode, replay_path, mock_scripts, fallback
```

权限分为 `read`、`compute`、`write`、`expensive`。工具还会经过外部 allowlist、参数
Schema、路径、时间和调用预算检查；Agent 工具包没有 shell/subprocess 桥。

### 8.5 三层 LLM Agent

三层可以独立开关：

1. Research Orchestration Agent：生成仅限验证集的研究计划并调用显式授权工具；
2. Risk Management Agent：生成风险预算，随后与管理员硬约束求交；
3. Hierarchical Strategy Agent：生成市场/层级预算和节奏，只作为约束融合。

预设：

```text
no_llm
research_only
risk_only
hierarchical_only
research_plus_risk
full_stack
custom
```

确定性无 LLM 路径：

```bash
cmag agent run --config configs/agents/phase7_no_llm.yaml
```

离线全栈：

```bash
cmag agent run --config configs/agents/phase7_full_stack_offline.yaml
```

层配置示例：

```yaml
preset: custom
layers:
  research:
    enabled: true
    mode: dry_run
    team: { ... }
  risk:
    enabled: true
    mode: enforced
    cadence: weekly
    team: { ... }
  hierarchical:
    enabled: false
    fusion: constraint
    cadence: monthly
```

Research 模式：

- `plan_only`：不能暴露可执行工具；
- `dry_run`：不能授予 `write` 或 `expensive` 权限；
- `execute`：调用 `train_rl`/`tune_rl` 前必须有 `estimate_compute_budget`，同时显式
  授予 `expensive` 权限和正数调用预算。

Risk 模式为 `advisory` 或 `enforced`。两个及以上 Risk Agent 必须使用
`most_conservative`。Risk Agent 失效时默认禁止新增头寸。

Risk 融合示例：

```text
effective_cash_floor = max(agent_cash_floor, 1 - risk_budget)
```

审计中会分别记录 Agent 值、风险预算隐含值、最终值、`max` 算子和原因
`Invested capital cannot exceed risk budget.`。

### 8.6 在线 DeepSeek

安装：

```bash
python -m pip install -e ".[llm]"
```

Linux/macOS：

```bash
export DEEPSEEK_API_KEY="<从安全凭据系统注入>"
export DEEPSEEK_BASE_URL="https://api.deepseek.com"
cmag agent provider-check \
  --config configs/agents/provider_online_deepseek.yaml
cmag agent run --config configs/agents/full_stack.yaml
```

PowerShell：

```powershell
$env:DEEPSEEK_API_KEY = "<从安全凭据系统注入>"
$env:DEEPSEEK_BASE_URL = "https://api.deepseek.com"
cmag agent provider-check `
  --config configs/agents/provider_online_deepseek.yaml
cmag agent run --config configs/agents/full_stack.yaml
```

运行结束后可从当前 shell 删除密钥：

```powershell
Remove-Item Env:DEEPSEEK_API_KEY
```

或：

```bash
unset DEEPSEEK_API_KEY
```

禁止使用以下形式：

```text
在 YAML 中保存任何明文密钥
在命令参数中传入任何明文密钥
git add .env
```

`provider-check` 验证 Provider、结构化输出、工具调用、审计和 Replay 闭环。在线响应
必须通过 Pydantic Schema；失败时使用声明的静态安全回退。

### 8.7 多 Agent 审计字段

聚合结果应区分配置与实际结果：

```json
{
  "configured_conflict_policy": "reject",
  "conflict_detected": false,
  "aggregate_decision": "approve",
  "selected_directive_confidence": 0.85,
  "committee_confidence": 0.50,
  "confidence_aggregation": "minimum"
}
```

动作投影还会记录主导原因和次要原因。不要把
`configured_conflict_policy=reject` 误解为本轮决策已被拒绝。

## 9. 超参数优化

### 9.1 三个独立组件

```text
SearchAlgorithm
→ TrialSuggestion
→ TrialScheduler
→ Local/Ray Trial Executor
→ train/validation Objective
→ SQLite StudyStore
```

搜索器负责候选点；调度器负责停止、提升、暂停或 exploit；执行器负责本地或 Ray
资源放置。三者不能混为一体。

### 9.2 搜索算法

`searcher.type` 的准确配置值：

| 算法 | 配置值 |
|---|---|
| Random Search | `random` |
| Grid Search | `grid` |
| TPE | `tpe` |
| CMA-ES | `cma_es` |
| NSGA-II | `nsga_ii` |
| Particle Swarm Optimization | `pso` |
| Genetic Algorithm | `genetic` |
| Differential Evolution | `differential_evolution` |
| Simulated Annealing | `simulated_annealing` |

### 9.3 资源调度器

`scheduler.type`：

```text
fifo
median
asha
hyperband
pbt
```

ASHA、HyperBand 和 PBT 只拥有资源/停止/提升/扰动权限，不产生初始候选点。

### 9.4 CPU HPO

```bash
cmag tune --config configs/tune/ppo_pso_quickstart.yaml
```

更完整的 CPU 示例：

```bash
cmag tune --config configs/tune/ppo_pso_cpu.yaml
```

主要配置结构：

```yaml
study_name: my-ppo-study
output_dir: runs/tuning
storage_path: runs/tuning/my-ppo-study.sqlite3
max_trials: 8
batch_size: 4
directions: [maximize]

search_space:
  parameters:
    learning_rate:
      kind: float
      low: 0.0001
      high: 0.001
      log: true
    n_steps:
      kind: int
      low: 8
      high: 64
      step: 8
    batch_size:
      kind: int
      low: 4
      high: 8
      step: 4
    policy:
      kind: categorical
      choices: [mlp]
  constraints:
    - batch_size <= n_steps

searcher:
  type: pso
  seed: 1024
  population_size: 4

scheduler:
  type: asha
  grace_period: 16
  max_resource: 64
  reduction_factor: 2

executor:
  type: local

objective:
  type: ppo_validation
  base_train_config: ../train/ppo_tune_smoke.yaml
  budget_stage: stage_a
  seeds: [1024]
  walk_forward_folds: 1
  total_timesteps: 64
  mode: robust
  include_training_time: false

selection:
  strategy: primary

retrain_locked: true
retrain_seed: 7777
retrain_timesteps: 64
```

参数类型为 `float`、`int`、`categorical`、`bool`。条件与跨参数约束由受限 AST
解释器处理，不使用 Python `eval`。

### 9.5 Stage A 与 Stage B

- `stage_a`：CPU 契约和开发 smoke，可使用较小的 seed/fold 预算；
- `stage_b`：正式选择，至少五个不同 seed、至少两个 expanding-train /
  forward-validation fold。

正式比较应使用 Stage B。默认稳健目标综合验证 Sharpe、最大回撤、换手和跨种子不
稳定性。多目标模式可使用 `primary`、`weighted` 或 `pareto_first` 选择策略。

锁定参数会使用未参与 HPO 的 `retrain_seed` 独立重训。只有重训和配置锁定完成后，
才能用 `cmag evaluate` 访问测试集；测试结果不得写回 Study。

### 9.6 Study 恢复

Study 使用版本化 SQLite，保存候选参数、状态、指标、资源、错误以及搜索器/调度器
Checkpoint。用完全相同的 `study_name`、数据库和配置重新运行 `cmag tune` 可恢复
Study。以下情况应停止而不是强行继续：

- 配置指纹改变；
- 数据 Manifest 改变；
- 数据库版本高于当前软件支持版本；
- 搜索器、调度器或目标定义改变；
- 已有 Trial 与当前参数空间不一致。

## 10. 产物验证与计算复现

### 10.1 仅验证产物完整性

```bash
cmag reproduce \
  --run-id repro-ppo-quickstart \
  --verify-only
```

该模式验证：

- run fingerprint 和 `run_manifest.json`；
- TrainerConfig 与 Dataset Manifest 哈希；
- Checkpoint SHA-256 与可加载性；
- 训练分区；
- 网络、测试指标与账户状态边界。

结果等级是 `artifact_verified`，并明确：

```json
{
  "verification_mode": "artifact_integrity",
  "artifact_integrity_verified": true,
  "computational_replay_executed": false
}
```

这不是完整计算复现。

### 10.2 执行计算重放

```bash
cmag reproduce \
  --run-id repro-ppo-quickstart \
  --execute \
  --compare \
  --tolerance-config configs/reproduction/phase11_cpu.yaml
```

`--execute` 与 `--compare` 必须同时出现。流程为：

1. 验证源运行完整性；
2. 读取源运行的已解析配置和相同 seed；
3. 验证原数据 Manifest；
4. 创建全新的隔离重放目录；
5. 只重建训练和验证环境；
6. 重新训练、验证并保存 Checkpoint、Metrics、Trades、Weights 和审计；
7. 比较原运行与重放运行；
8. 写入 `reproduction_comparison.json`。

默认目录：

```text
runs/reproductions/<source-run-id>/<replay-run-id>/
├── source_run.json
├── config.resolved.yaml
├── resolved_config.json
├── run_manifest.json
├── run_summary.json
├── training_artifact.json
├── reproduction_audit.jsonl
├── checkpoints/final_model.zip
├── validation/
│   ├── metrics.json
│   ├── trades.json
│   └── weights.json
└── reproduction_comparison.json
```

可为新目录指定唯一名称：

```bash
cmag reproduce \
  --run-id repro-ppo-quickstart \
  --execute \
  --compare \
  --replay-run-id replay-repro-ppo-quickstart-002
```

不能选择已存在的重放目录，也不能覆盖源运行。

### 10.3 复现等级

```text
artifact_verified
bitwise_reproduced
numerically_reproduced
statistically_reproduced
failed
```

- `bitwise_reproduced`：核心文件或数组逐位一致；
- `numerically_reproduced`：硬性不变量一致，关键指标在容差内；
- `statistically_reproduced`：至少三次可比重放的分布满足冻结统计规则；
- `failed`：完整性、不变量、容差、执行或源目录不可变性检查失败。

Phase 11 CPU quickstart 至少要求 `numerically_reproduced`。

比较指标：

```text
validation.mean_return
validation.mean_reward
validation.max_drawdown
validation.mean_turnover
validation.total_cost
trained_timesteps
checkpoint_loadability
```

必须完全一致的标识还包括算法、Dataset Manifest 哈希、TrainerConfig 哈希和执行协议。
默认数值容差位于 `configs/reproduction/phase11_cpu.yaml`。

计算重放不会创建测试环境、调用 LLM、访问网络或修改外部账户。失败目录会作为证据
保留。

## 11. 报告与只读服务

### 11.1 查看单个运行

```bash
cmag report --run-id repro-ppo-quickstart
```

指定不同根目录：

```bash
cmag report \
  --workspace-root . \
  --runs-root runs \
  --run-id repro-ppo-quickstart
```

### 11.2 查看运行索引

```bash
cmag report runs --workspace-root . --runs-root runs
```

索引使用白名单提取有限元数据，不暴露原始 Prompt、Provider 响应、Checkpoint、
密钥、任意配置或任意运行文件。

### 11.3 生成 SoftwareX 报告

```bash
cmag report softwarex --config configs/reporting/softwarex.yaml
```

输出通常位于 `reports/<report_id>/`：

```text
report.md
report.html
runs.html
report_data.json
run_index.json
tables/*.csv
figures/*.svg
manifest.json
```

配置中的 `completed` 实验必须引用真实证据；未完成实验只能标记为 `planned` 或
`partial`。报告不会为缺失证据生成零值、排名或“最佳模型”。Benchmark 表始终带有
`selection_authority: false`，不能用于 HPO。

### 11.4 启动只读服务

```bash
python -m pip install -e ".[service]"
cmag service run --config configs/reporting/service.yaml
```

默认地址：

```text
http://127.0.0.1:8000
```

主要只读端点：

```text
GET /health
GET /api/runs
GET /api/runs/{run_id}
GET /api/reports
GET /reports/{report_id}/
```

默认 `allow_remote: false` 且关闭 OpenAPI 文档。若改为非 loopback 地址，必须显式设
`allow_remote: true`，并在外层提供认证、TLS、防火墙和访问日志；软件本身不声称
提供生产级认证。

## 12. Docker

### 12.1 构建基础镜像

```bash
docker build \
  --pull \
  --no-cache \
  --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
  --build-arg CMAG_EXTRAS=service \
  -t crossmarket-agent-gym:1.0.0-rc2 .
```

验证：

```bash
docker run --rm crossmarket-agent-gym:1.0.0-rc2 --version
docker run --rm \
  --network none \
  --cpus 2 \
  --memory 7g \
  -e CUDA_VISIBLE_DEVICES="" \
  -e NVIDIA_VISIBLE_DEVICES=void \
  crossmarket-agent-gym:1.0.0-rc2 \
  quickstart --smoke-steps 64
```

### 12.2 构建带 RL/HPO/LLM 的 CPU 镜像

```bash
docker build \
  --pull \
  --no-cache \
  --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
  --build-arg CMAG_EXTRAS=rl,hpo,llm,service \
  -t crossmarket-agent-gym:1.0.0-rc2-rl .
```

镜像使用固定 UID `10001` 的非 root 用户 `cmag`。基础镜像包含 `configs/` 和
`data/sample/`；Mock/Replay 示例资源随 wheel 打包。

### 12.3 挂载运行目录

使用 Docker named volume 可避免 Linux bind mount 权限问题：

```bash
docker volume create cmag-runs
docker run --rm \
  --network none \
  --cpus 2 \
  --memory 7g \
  -e CUDA_VISIBLE_DEVICES="" \
  -e NVIDIA_VISIBLE_DEVICES=void \
  -v cmag-runs:/workspace/runs \
  crossmarket-agent-gym:1.0.0-rc2-rl \
  train --config configs/train/ppo_quickstart.yaml
```

如需挂载本地原始数据，务必只读：

```bash
docker run --rm \
  --network none \
  --cpus 2 \
  --memory 7g \
  --mount type=bind,src="$(pwd)/stock_data",dst=/workspace/stock_data,readonly \
  -v cmag-runs:/workspace/runs \
  crossmarket-agent-gym:1.0.0-rc2-rl \
  data validate --config configs/data/local_stock_data_full.yaml
```

在线 Agent 运行不能使用 `--network none`，但密钥仍只能通过运行时环境注入，优先
使用 Docker Secret 或编排平台 Secret，不要通过 Dockerfile `ARG`/`ENV` 固化。

`.dockerignore` 会排除凭据、原始市场数据、runs、reports、results、测试和论文草稿，
防止进入构建上下文。

## 13. 远程 GPU 与 Ray

### 13.1 基础远程流程

在远程主机准备项目目录和 Python 3.12 环境。推荐通过 SSH key 登录；不要把密码写入
脚本、URL、命令历史或仓库。

```bash
ssh <user>@<gpu-host>
cd <remote-project-root>/CrossMarketAgentGym
export PIP_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"
python -m pip install -c constraints-gpu.txt -e ".[rl,ray]"
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.device_count())"
```

若已有固定解释器：

```bash
<python-env>/bin/python -m pip install \
  -c constraints-gpu.txt -e ".[rl,ray]"
<python-env>/bin/python -c \
  "import torch; print(torch.cuda.is_available(), torch.cuda.device_count())"
```

代码、配置、Dataset Manifest 和实验协议应通过 Git commit/hash 绑定。`stock_data/`、
`data/processed/`、`runs/` 与 `results/` 不进入 Git，应通过受控文件传输并在远端
重新校验 SHA-256。

### 13.2 单 GPU 训练

复制训练配置并设置：

```yaml
trainer:
  device: cuda
```

然后：

```bash
cmag data validate --config <数据配置>
cmag env check --config <环境配置>
cmag train --config <CUDA训练配置>
```

不要使用 `device: auto` 作为需要严格硬件归因的正式实验配置；显式选择 `cpu` 或
`cuda`，并检查 `run_summary.json` 中的设备、PyTorch、CPU/GPU 型号与运行时。

### 13.3 Ray 多 GPU HPO

示例配置将 PSO、ASHA 和 Ray 保持为三个独立顶层对象：

```bash
ray start --head
cmag tune --config configs/tune/ppo_pso_ray_gpu.yaml
```

配置要点：

```yaml
searcher:
  type: pso

scheduler:
  type: asha

executor:
  type: ray
  address: auto
  num_cpus_per_trial: 2
  num_gpus_per_trial: 1
  shutdown_on_close: false
```

所有 Ray worker 必须看到完全相同的：

- 代码 commit 和干净源码状态；
- 数据目录与 Dataset Manifest；
- 输出目录和 SQLite Study；
- 训练配置、实验协议与随机种子；
- CUDA/PyTorch 环境。

不要把 LLM 密钥放入 Ray runtime environment。Ray 只负责 Trial 放置，不获得测试
指标、搜索权、调度权或账户修改权。

## 14. 运行审计与证据保存

每次需要复核或论文引用的运行至少应保存：

```text
run ID
resolved configuration
Dataset Manifest and hash
protocol path and hash
code commit and source state
seed
Python/PyTorch/SB3/NumPy versions
CPU/GPU identity
started/finished time and duration
training/validation/test partition authority
Checkpoint and artifact SHA-256
network/test/account-state access declarations
metrics, trades, weights, audit and resource logs
run_manifest.json
```

推荐检查：

```bash
cmag report --run-id <run-id>
cmag reproduce --run-id <run-id> --verify-only
```

受控运行器中若镜像内没有 `.git`，可显式提供：

```bash
export CMAG_CODE_COMMIT="<40位Git commit>"
export CMAG_SOURCE_STATE="clean"
```

这些值必须来自执行系统，不得手工伪造。论文中的每个数字都应能追溯到 run ID 和来源
文件。

## 15. 正式实验操作纪律

开发 quickstart、调试运行、单 seed 最佳结果和 Phase 10/11 复现结果不能转为正式
实验结果。

当前 Phase 12 冻结输入位于：

```text
experiments/protocol_v4.yaml
experiments/protocol_v4.sha256
experiments/run_matrix_v6.json
experiments/run_matrix_v6.sha256
experiments/agents/prompt_bundle_v1.json
experiments/data/source_inventory_v3.json
experiments/data/dataset_snapshot_v3.json
```

已有机器门禁完成，但独立复核仍是 Phase 12 的退出条件。在真实独立复核完成、
P0/P1 为零并重新生成通过的阶段汇总之前：

- 不得进入 Phase 13；
- 不得冻结或发布正式 Benchmark；
- 不得把临时结果写入论文；
- 不得编辑冻结协议、矩阵或哈希；
- 发现问题时应创建新协议/矩阵修订版，并保留 supersession 记录。

复核人员应使用独立环境验证数据哈希、协议、运行清单、泄漏边界、会计、Agent Replay、
HPO 测试隔离、统计表和图的来源，而不是只检查最终指标。

## 16. 测试、静态检查与开发

安装开发依赖后执行：

```bash
pytest
ruff check .
mypy src
python scripts/verify_docs.py
```

常用定向测试：

```bash
pytest tests/unit
pytest tests/integration -m integration
pytest -k "leakage or accounting or reproduction"
```

项目默认启用分支覆盖率并要求总覆盖率至少 85%。正式阶段完成前应运行完整测试、
Ruff 和 strict mypy；不能用局部测试结果替代完整门禁。

验证冻结公共接口：

```bash
cmag release freeze --workspace-root .
```

`release freeze` 默认只验证。只有维护者在经过审查、确实需要更新冻结清单时才使用：

```bash
cmag release freeze --workspace-root . --write
```

## 17. 本地发行检查

以下操作只构建和验证本地产物，不发布：

```bash
python scripts/verify_docs.py
cmag release freeze --workspace-root .
cmag release check --workspace-root .
python -m build
python -m twine check dist/*.whl dist/*.tar.gz
cmag release verify --dist-dir dist
cmag release manifest --dist-dir dist
```

PowerShell 的 Twine 检查可写为：

```powershell
Get-ChildItem dist\*.whl, dist\*.tar.gz |
  ForEach-Object { python -m twine check $_.FullName }
```

发布 Git tag、PyPI、GitHub Release 或 Zenodo 都是外部状态变更，必须取得明确授权。
已经发布的版本和证据不可覆盖；缺陷版本应说明原因、必要时 yank，并发布新补丁版本。

## 18. 常见故障

### 18.1 `run already exists`

原因：运行 ID 是不可变证据。

处理：修改配置中的 `run_name`/`run_id`/`study_name`，或使用新 workspace。不要覆盖
旧目录。

### 18.2 CPU 主机安装了 CUDA 包

优先使用 `environment-cpu.yml` 或 `constraints-cpu.txt`，然后检查：

```bash
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

CPU 证据要求 `False`。

### 18.3 在线 Agent 报密钥缺失

确认已安装 `llm` extra，并在当前进程环境设置 `DEEPSEEK_API_KEY`。不要把密钥复制进
YAML。Mock/Replay 不需要密钥。

### 18.4 Provider 返回非结构化内容

运行 `cmag agent provider-check`。检查模型是否严格为 `deepseek-v4-pro`、endpoint
是否为 `/chat/completions`、结构化输出模式是否与 Provider 兼容。失败应触发静态
安全回退，而不是跳过 Schema。

### 18.5 SB3 把 OHLCV 当图像

默认 PPO/SAC/TD3 配置使用：

```yaml
observation:
  market_window_layout: flat
trainer:
  policy: mlp
```

若必须使用 `tensor`，配置 `shared_mlp`、`transformer` 或自定义
`BaseFeaturesExtractor`。不要把 OHLCV 改为图像像素。

### 18.6 Dataset Manifest 哈希错误

停止训练和调参。检查文件传输、路径、字节数和来源。确认数据确实需要变更后创建新的
版本化 Manifest，不要手工修改旧哈希。

### 18.7 会计误差超过 `1e-8`

立即停止该运行。保存 audit、trades、weights、配置和数据哈希，先复现失败步骤。不要
通过调大 `accounting_tolerance` 掩盖错误。

### 18.8 HPO Study 无法恢复

确认软件版本、配置指纹、搜索空间、搜索器、调度器、数据 Manifest 和 SQLite
`user_version` 一致。不要迁移或直接修改数据库，除非已有审查过的迁移脚本。

### 18.9 Ray 找不到 GPU

检查：

```bash
nvidia-smi
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.device_count())"
ray status
```

再核对每 Trial 的 `num_gpus_per_trial`、CUDA 环境、Ray worker 路径和数据可见性。

### 18.10 Docker 挂载目录不可写

容器以 UID `10001` 运行。优先使用 Docker named volume；使用 bind mount 时，在主机
上为该 UID 提供最小必要写权限。原始数据目录保持只读。

### 18.11 报告缺少某个运行

确认 run ID 存在、`run_manifest.json` 完整、运行类型属于报告白名单、配置中的
`runs_root` 和 `include_run_ids` 正确。报告生成器不会读取任意未知文件。

## 19. 命令速查

```bash
# 版本与帮助
cmag --version
cmag --help

# CPU 打包验证
cmag quickstart --smoke-steps 64

# 数据与环境
cmag data validate --config configs/data/sample.yaml
cmag env check --config configs/env/sample_cross_market.yaml

# 训练与一次性锁定测试
cmag train --config configs/train/ppo_quickstart.yaml
cmag evaluate --run-id <run-id>

# Agent
cmag agent provider-check --config configs/agents/provider_offline.yaml
cmag agent run --config configs/agents/runtime_single_offline.yaml
cmag agent run --config configs/agents/runtime_team_offline.yaml
cmag agent run --config configs/agents/phase7_full_stack_offline.yaml

# HPO
cmag tune --config configs/tune/ppo_pso_cpu.yaml

# 报告
cmag report --run-id <run-id>
cmag report runs --workspace-root . --runs-root runs
cmag report softwarex --config configs/reporting/softwarex.yaml
cmag service run --config configs/reporting/service.yaml

# 复现
cmag reproduce --run-id <run-id> --verify-only
cmag reproduce --run-id <run-id> --execute --compare

# 发行检查
cmag release freeze --workspace-root .
cmag release check --workspace-root .
cmag release verify --dist-dir dist
cmag release manifest --dist-dir dist
```

## 20. 延伸文档

- [安装](installation.md)
- [CPU quickstart](quickstart.md)
- [CLI 参考](cli-reference.md)
- [数据契约](data-contract.md)
- [环境与会计契约](environment-contract.md)
- [训练契约](training-contract.md)
- [AgentRuntime 契约](agent-runtime-contract.md)
- [Provider 与工具契约](provider-tool-contract.md)
- [三层指令融合契约](directive-fusion-contract.md)
- [HPO 契约](tuning-contract.md)
- [计算复现](reproducibility.md)
- [报告与服务](reporting-service-contract.md)
- [Ray/GPU 扩展](scaling.md)
- [安全边界](security.md)
- [发行与归档](release.md)
- [故障排查](troubleshooting.md)
