# CrossMarketAgentGym 详细执行报告（供 Codex 直接实施）

## 0. 文档目的

本报告定义一个面向 A 股、港股、日股和美股日度 OHLCV 数据的开源科研软件工程：

**CrossMarketAgentGym：多市场深度强化学习、LLM Agent 编排与启发式超参数优化平台。**

Codex 不得把项目降级为单个 Notebook、单一 PPO 示例或只有界面的演示程序。最终软件必须：

1. 可作为 Python 包安装；
2. 提供 Gymnasium 兼容环境；
3. 支持 PPO、SAC、TD3；
4. 实现三个层次的 LLM Agent，并允许任意启停和组合；
5. 统一单 Agent 与多 Agent 投资委员会，允许自定义类型、数量和协作拓扑；
6. 提供可插拔的启发式、贝叶斯和进化式超参数搜索；
7. 支持多市场日历、币种、交易限制和无泄漏执行；
8. 所有实验可审计、可重现、可导出；
9. 具备 SoftwareX 投稿所需的软件工程质量、示例、测试和文档。

---

# 1. 核心决策

## 1.1 三层 LLM Agent 全部实现

三个层次全部实现，但采用插件化模式：

| 模式 | 功能 | 是否参与交易决策 |
|---|---|---:|
| `off` | 完全关闭 LLM | 否 |
| `research` | 数据诊断、实验配置、训练与报告编排 | 否 |
| `risk` | 输出结构化风险预算和约束 | 间接参与 |
| `hierarchical` | 输出高层市场状态、预算或再平衡策略 | 是 |
| `full` | 三层全部启用 | 是 |

三层分别为：

1. **Research Orchestration Agent**：研究流程编排；
2. **Risk Management Agent**：生成结构化风险指令；
3. **Hierarchical Strategy Agent**：低频高层决策，DRL 负责具体权重。

LLM 不得直接修改环境账户状态，不得绕过风险投影层，不得把未经验证的自由文本作为交易动作。

## 1.2 单 Agent 与多 Agent 统一

实现统一 `AgentRuntime`：

- 单 Agent 是只有一个实例的团队；
- 多 Agent 按配置拓扑通信；
- 用户通过 YAML 定义 Agent 类型、数量、模型、工具、权重、轮数和裁决机制；
- 同类 Agent 可创建多个实例，例如 3 个风险 Agent；
- 支持用户注册自定义 Agent 类型。

## 1.3 强化学习任务

主任务为连续投资组合配置。动作：

```text
[cash_weight, asset_1_weight, ..., asset_n_weight]
```

默认多头、含现金、总权重为 1。卖空、杠杆、单资产上限、市场上限均配置化。所有原始动作必须经过确定性的约束投影。

## 1.4 日度执行协议

默认协议：

1. 状态使用截至 `t` 日收盘后可获得的信息；
2. `t` 日收盘后生成目标权重；
3. `t+1` 日对应市场开盘执行；
4. 用 `t+1` 的价格变化计算收益；
5. 休市、停牌、涨跌停或 T+1 导致无法成交时，保留原持仓并记录拒单原因。

协议名称写入配置和审计日志，禁止“同一收盘价既产生信号又完成无摩擦成交”。

---

# 2. 范围与非目标

## 2.1 必须实现

- 多市场 OHLCV 标准化；
- 交易日历、交易掩码和汇率接口；
- 复权状态及数据质量报告；
- Gymnasium 投资组合环境；
- 成本、滑点和市场限制；
- DRL 适配器；
- walk-forward、股票留出、市场留出；
- 三层 LLM Agent；
- 单/多 Agent 统一运行时；
- HPO 搜索和资源调度；
- CLI、Python API；
- 审计及 HTML/Markdown 报告；
- 自动化测试和公开小样本。

## 2.2 首版非核心

- 分钟级或订单簿高频交易；
- 实盘券商下单；
- 无约束 LLM 直接交易；
- 完整新闻/财报多模态；
- 强制多机训练；
- 复杂交易终端前端。

---

# 3. 技术栈与版本策略

基础技术栈：

- Python 3.11；
- Gymnasium；
- Stable-Baselines3；
- PyTorch；
- Pydantic v2；
- pandas 或 Polars、NumPy；
- PyArrow/Parquet；
- DuckDB 或 SQLite；
- Optuna；
- Ray Tune（可选并行、ASHA、HyperBand、PBT）；
- Typer、FastAPI、Jinja2；
- pytest、Hypothesis、Ruff、mypy/pyright。

Codex 首先建立依赖兼容性测试，不盲目使用最新版本。交付：

```text
pyproject.toml
uv.lock 或 poetry.lock
constraints-cpu.txt
constraints-gpu.txt
```

CI 至少覆盖 Python 3.11、Linux、CPU。

---

# 4. 项目目录

```text
crossmarket-agent-gym/
├── pyproject.toml
├── README.md
├── LICENSE
├── CITATION.cff
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── CHANGELOG.md
├── Dockerfile
├── configs/{data,env,train,tune,agents,examples}/
├── data/sample/
├── docs/
├── examples/
├── src/crossmarket_agentgym/
│   ├── cli/
│   ├── config/
│   ├── data/{adapters,schemas,calendars,fx,quality,manifests}/
│   ├── features/
│   ├── environments/
│   ├── rl/{trainers,policies,callbacks}/
│   ├── tuning/{searchers,schedulers,reports}/
│   ├── agents/{providers,tools,roles,aggregation,guardrails}/
│   ├── evaluation/
│   ├── reporting/
│   ├── audit/
│   ├── api/
│   └── utils/
└── tests/{unit,property,integration,regression,leakage,agents,tuning}/
```

---

# 5. 数据层

## 5.1 OHLCV Schema

```python
class OHLCVRecord(BaseModel):
    trade_date: date
    symbol: str
    market: Literal["CN", "HK", "JP", "US"]
    exchange: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    currency: str
    timezone: str
    adjusted: bool
    source: str
```

可选：`adjusted_close`、`turnover`、`suspension_flag`、`limit_up`、`limit_down`、`tradable`。

必须验证：

- `high >= max(open, close, low)`；
- `low <= min(open, close, high)`；
- 价格和成交量非负；
- 主键不重复；
- 日期排序；
- 市场、币种、时区映射一致；
- 异常不得静默删除。

## 5.2 数据布局

```text
dataset_root/
├── market=CN/year=2024/*.parquet
├── market=HK/year=2024/*.parquet
├── market=JP/year=2024/*.parquet
├── market=US/year=2024/*.parquet
├── instruments.parquet
├── fx_rates.parquet
└── dataset_manifest.json
```

Manifest 记录范围、股票列表、SHA-256、来源、导入时间、复权规则、缺失率、Schema 和软件版本。

## 5.3 交易日历

```python
class MarketCalendar(Protocol):
    def is_trading_day(self, value: date) -> bool: ...
    def sessions(self, start: date, end: date) -> list[date]: ...
    def next_session(self, value: date) -> date: ...
    def previous_session(self, value: date) -> date: ...
```

支持 `native`、`union`、`intersection`、`scheduled_rebalance`；后续扩展 UTC 事件驱动模式。首版多市场环境用 `union + tradable_mask`，禁止把休市日前向填充后当作可交易日。

---

# 6. Gymnasium 环境

```python
class CrossMarketPortfolioEnv(gymnasium.Env):
    metadata = {"render_modes": ["human", "ansi", "rgb_array"]}

    def reset(self, *, seed=None, options=None):
        ...

    def step(self, action):
        ...
```

返回值严格为：

```python
observation, info = env.reset(seed=seed)
observation, reward, terminated, truncated, info = env.step(action)
```

Observation 使用 `spaces.Dict`：

```text
market_window: [N, L, F]
portfolio_weights: [N + 1]
cash_ratio: [1]
tradable_mask: [N]
market_ids: [N]
currency_ids: [N]
risk_state: [K]
time_features: [T]
```

动作处理：

```text
raw action
→ 数值清洗
→ softmax/有符号归一化
→ tradable mask
→ 市场规则
→ 确定性风险投影
→ execution engine
```

`info` 返回原动作、归一化权重、投影权重、裁剪原因、成交额、成本、滑点、换手、组合价值、回撤及市场敞口。

内置 Reward：

- LogReturn；
- ReturnMinusCost；
- RiskAdjusted；
- DifferentialSharpe；
- DrawdownPenalty；
- CVaRPenalty。

规则插件：

- LongOnly；
- MaxAssetWeight；
- MaxMarketWeight；
- Leverage；
- CashFloor；
- TurnoverLimit；
- TradableMask；
- LotSize；
- TPlusOne；
- PriceLimit；
- Suspension。

市场规则参数必须配置化，不能硬编码成永恒事实。


---

# 7. DRL 层

## 7.1 统一 Trainer

```python
class RLTrainer(Protocol):
    algorithm_name: str

    def train(self, env, config, callbacks) -> TrainingArtifact: ...
    def evaluate(self, env, checkpoint) -> EvaluationResult: ...
    def save(self, artifact, path) -> None: ...
    def load(self, path): ...
```

首版：

- PPO；
- SAC；
- TD3；
- 可选 A2C。

非 RL 基准：

- Cash；
- Buy and Hold；
- Equal Weight；
- Risk Parity；
- Mean-Variance；
- Momentum；
- Minimum Variance。

Policy 提供 MLP、共享变量 MLP、Transformer encoder，并保留 IR-MoE 适配接口。IR-MoE 不得成为唯一策略。

训练回调：

- checkpoint；
- validation evaluation；
- early stop；
- NaN/Inf guard；
- max drawdown guard；
- resource monitor；
- audit callback；
- metrics writer。

---

# 8. 三层 LLM Agent

## 8.1 Provider

```python
class LLMProvider(Protocol):
    def generate(
        self,
        messages: list[Message],
        response_schema: type[BaseModel] | None,
        tools: list[ToolDefinition] | None,
        generation_config: GenerationConfig,
    ) -> LLMResponse: ...
```

实现：

- `OpenAICompatibleProvider`；
- `MockProvider`；
- `ReplayProvider`；
- 可选云端 Provider。

Provider 配置必须记录模型、base URL、温度、token 上限、超时和重试。API key 只从环境变量读取。

## 8.2 第一层：Research Orchestration Agent

职责：

- 理解实验目标；
- 调用数据检查；
- 生成实验配置；
- 验证配置；
- 调用训练、调参和回测；
- 比较运行；
- 生成报告。

工具：

```text
inspect_dataset
validate_dataset
list_markets
list_symbols
create_split
validate_experiment_config
estimate_compute_budget
train_rl
tune_rl
evaluate_checkpoint
compare_runs
generate_report
```

模式：

- `plan_only`；
- `dry_run`；
- `execute`。

禁止直接改数据、绕过 Schema、无预算启动大任务、把验证结果冒充测试结果。

## 8.3 第二层：Risk Management Agent

输入结构化风险摘要：

```python
class RiskContext(BaseModel):
    portfolio_value: float
    current_drawdown: float
    rolling_volatility: float
    rolling_cvar: float
    turnover: float
    market_exposures: dict[str, float]
    asset_exposures: dict[str, float]
    liquidity_flags: dict[str, bool]
    regime_features: dict[str, float]
```

输出：

```python
class RiskDirective(BaseModel):
    risk_budget: float = Field(ge=0.0, le=1.0)
    max_asset_weight: float = Field(gt=0.0, le=1.0)
    max_market_weights: dict[str, float]
    cash_floor: float = Field(ge=0.0, le=1.0)
    max_turnover: float = Field(ge=0.0, le=2.0)
    allow_new_positions: bool
    rebalance_frequency: Literal["daily", "weekly", "monthly"]
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)
```

模式：

- `advisory`：只记录；
- `enforced`：经 Schema、边界和管理员政策合并后生效。

规则：

- LLM 失败时使用静态安全默认值；
- LLM 只能在管理员硬上限内调整，不能放宽绝对风险边界；
- 风险相关多 Agent 冲突默认采用最保守结果。

## 8.4 第三层：Hierarchical Strategy Agent

低频输出：

```python
class HierarchicalDirective(BaseModel):
    market_regime: Literal[
        "risk_on", "neutral", "risk_off", "high_volatility", "unknown"
    ]
    market_budgets: dict[str, float]
    sector_budgets: dict[str, float] | None
    global_risk_budget: float
    rebalance_interval: int
    objective_weights: dict[str, float]
    confidence: float
```

两种融合：

1. `constraint`：LLM 输出预算，DRL 权重经投影满足预算；
2. `conditioning`：高层指令编码后作为 policy 额外输入。

首版先完成 `constraint`，第二阶段完成 `conditioning`。

配置：

```yaml
llm_layers:
  research:
    enabled: true
    mode: execute
  risk:
    enabled: true
    mode: enforced
    cadence: weekly
  hierarchical:
    enabled: true
    fusion: constraint
    cadence: monthly
```

预设：

```text
no_llm
research_only
risk_only
hierarchical_only
research_plus_risk
full_stack
```

---

# 9. 单 Agent + 多 Agent 统一运行时

## 9.1 AgentSpec

```python
class AgentSpec(BaseModel):
    type: str
    name: str
    count: int = Field(default=1, ge=1, le=32)
    provider: str
    model: str
    prompt_template: str
    tools: list[str]
    weight: float = 1.0
    temperature: float = 0.0
    timeout_seconds: int = 120
    max_retries: int = 2
    enabled: bool = True
    metadata: dict[str, Any] = {}
```

`count=3` 创建 `risk_reviewer_0..2`，每个实例有独立 ID、seed、消息、状态、超时和重试。

内置类型：

- research_coordinator；
- data_quality；
- experiment_designer；
- environment_reviewer；
- training；
- hyperparameter_tuning；
- market_regime；
- risk_manager；
- portfolio_reviewer；
- backtest_auditor；
- report_writer；
- judge；
- custom。

## 9.2 TeamSpec

```python
class TeamSpec(BaseModel):
    topology: Literal[
        "single",
        "pipeline",
        "supervisor_worker",
        "committee_vote",
        "debate_then_judge",
        "map_reduce"
    ]
    agents: list[AgentSpec]
    supervisor: str | None
    judge: str | None
    max_rounds: int = 3
    quorum: float = 0.5
    conflict_policy: Literal[
        "weighted_vote",
        "majority_vote",
        "judge",
        "most_conservative",
        "reject"
    ]
    parallel: bool = True
```

默认团队：

```yaml
team:
  topology: supervisor_worker
  supervisor: coordinator
  max_rounds: 3
  agents:
    - type: research_coordinator
      name: coordinator
      count: 1
      tools: [inspect_dataset, validate_experiment_config, train_rl, tune_rl]
    - type: data_quality
      name: data_guard
      count: 1
      tools: [inspect_dataset, validate_dataset]
    - type: risk_manager
      name: risk_committee
      count: 3
      tools: [read_risk_report]
    - type: backtest_auditor
      name: audit_committee
      count: 2
      tools: [inspect_split, inspect_execution_log, compare_runs]
    - type: report_writer
      name: reporter
      count: 1
      tools: [read_metrics, read_audit]
```

支持 Python 注册和 entry point：

```python
agent_registry.register("custom_factor_reviewer", CustomFactorReviewer)
```

```toml
[project.entry-points."crossmarket_agentgym.agents"]
custom_factor_reviewer = "my_package.agent:CustomFactorReviewer"
```

## 9.3 冲突裁决

风险默认 `most_conservative`：

- 更高现金；
- 更低单资产上限；
- 更低市场上限；
- 更低换手；
- 禁止新增仓位优先。

研究配置使用 `judge` 或结构化 Schema 合并。禁止对任意自由文本直接多数投票。

---

# 10. 启发式超参数优化

## 10.1 架构

```text
SearchAlgorithm
→ TrialSuggestion
→ TrialScheduler
→ TrialRunner
→ ObjectiveEvaluator
→ StudyStore
```

接口：

```python
class SearchAlgorithm(Protocol):
    def initialize(self, search_space, study_state): ...
    def suggest(self, n: int = 1) -> list[TrialSuggestion]: ...
    def observe(self, results: list[TrialResult]) -> None: ...
    def state_dict(self) -> dict: ...
    def load_state_dict(self, state: dict) -> None: ...
```

搜索算法与资源调度器必须分开。

## 10.2 必须实现/适配

基础与贝叶斯：

1. Random Search；
2. Grid Search；
3. TPE；
4. CMA-ES；
5. NSGA-II。

自定义启发式：

6. Particle Swarm Optimization；
7. Genetic Algorithm；
8. Differential Evolution；
9. Simulated Annealing。

第二阶段实验性：

10. Grey Wolf Optimization；
11. Whale Optimization Algorithm。

GWO/WOA 标记 `experimental`，不能作为论文唯一优势。

## 10.3 调度器

- FIFO；
- Median Stopping；
- ASHA；
- HyperBand；
- Population Based Training。

建立搜索器—调度器兼容矩阵。ASHA/HyperBand 属于早停与资源分配，不应伪装成搜索器。

## 10.4 搜索空间

```python
class ParameterSpec(BaseModel):
    name: str
    kind: Literal["float", "int", "categorical", "bool"]
    low: float | int | None
    high: float | int | None
    choices: list[Any] | None
    log: bool = False
    step: float | int | None = None
    condition: str | None = None
```

PPO 示例：

```yaml
search_space:
  learning_rate:
    kind: float
    low: 1.0e-5
    high: 3.0e-3
    log: true
  n_steps:
    kind: categorical
    choices: [128, 256, 512, 1024, 2048]
  batch_size:
    kind: categorical
    choices: [32, 64, 128, 256]
  gamma:
    kind: float
    low: 0.90
    high: 0.9999
  gae_lambda:
    kind: float
    low: 0.80
    high: 1.0
  clip_range:
    kind: float
    low: 0.05
    high: 0.40
```

约束：

- `batch_size <= n_steps * n_envs`；
- 不同算法使用不同空间；
- 非法候选训练前拒绝。

## 10.5 目标函数

默认多 seed + walk-forward。

单目标：

```text
score =
median_validation_sharpe
- 0.50 * median_validation_max_drawdown
- 0.05 * median_validation_turnover
- 0.25 * std_sharpe_across_seeds
```

多目标：

- 最大化 median Sharpe；
- 最小化最大回撤；
- 最小化换手；
- 最小化 seed 不稳定性；
- 可选最小化训练时间。

NSGA-II 输出 Pareto front，最终选择规则配置化。

## 10.6 防过拟合

- 训练集训练；
- 验证集调参；
- 测试集只在锁定配置后评估；
- walk-forward；
- 至少 3 个 seed；
- 保存失败 trial；
- 禁止 HPO 读取测试指标；
- 最终配置独立重训。

两阶段预算：

- Stage A：缩短 timesteps、减少股票/fold、早停；
- Stage B：完整股票池、完整 walk-forward、至少 5 seed。

每个搜索器测试：

- Sphere；
- Rosenbrock；
- 混合空间；
- 固定 seed；
- checkpoint/resume；
- 边界；
- 失败容错；
- 小型 PPO 端到端。

---

# 11. Agent 与 HPO 融合

`HyperparameterTuningAgent` 只负责：

- 根据预算选搜索器；
- 选择单/多目标；
- 阅读中间结果；
- 提出搜索空间补丁；
- 生成调参报告。

不得伪造 trial 结果。

```yaml
tuning_agent:
  enabled: true
  permissions:
    choose_searcher: true
    modify_search_space: true
    stop_study: false
  hard_budget:
    max_trials: 100
    max_gpu_hours: 48
```

空间修改必须成为 `SearchSpacePatch`，通过 Schema 和管理员边界检查，并写入审计日志。


---

# 12. 工具系统

```python
class ToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    permission: Literal["read", "compute", "write", "expensive"]
    timeout_seconds: int
```

权限：

- `read`：数据清单、指标；
- `compute`：检查和评估；
- `write`：配置和报告；
- `expensive`：训练和调参。

工具结果：

```python
class ToolResult(BaseModel):
    success: bool
    data: dict[str, Any] | None
    artifact_paths: list[str]
    warnings: list[str]
    error_code: str | None
    error_message: str | None
    duration_seconds: float
```

用户文本不得直接成为 shell 命令。

---

# 13. 审计、复现与安全

每次运行：

```text
runs/<run_id>/
├── config.resolved.yaml
├── config.sha256
├── dataset_manifest.json
├── environment.json
├── git_commit.txt
├── seeds.json
├── training/
├── checkpoints/
├── evaluation/
├── trades.parquet
├── weights.parquet
├── metrics.json
├── agent/
│   ├── messages.jsonl
│   ├── tool_calls.jsonl
│   ├── directives.jsonl
│   └── provider_metadata.json
├── tuning/
└── report.html
```

必须记录数据哈希、commit、依赖、硬件、seed、环境、LLM 模型、Prompt 版本、工具调用、原始/投影指令、失败和回退。

安全要求：

- 禁止任意 `eval`；
- 路径限制在工作区；
- 参数必须 Pydantic 验证；
- 默认禁用网络下载工具；
- API key 只读环境变量；
- 日志不写密钥；
- 提供 LLM Replay 离线重放。

---

# 14. CLI

```bash
cmag data validate --config configs/data/sample.yaml
cmag env check --config configs/env/cross_market.yaml
cmag train --config configs/train/ppo.yaml
cmag evaluate --run-id <RUN_ID>
cmag tune --config configs/tune/ppo_pso.yaml
cmag agent run --config configs/agents/research_single.yaml
cmag agent run --config configs/agents/investment_committee.yaml
cmag report --run-id <RUN_ID>
cmag reproduce --run-id <RUN_ID>
```

`cmag env check` 执行：

- 自定义检查；
- SB3 `check_env`；
- 随机动作 smoke test；
- 会计恒等式；
- NaN/Inf 检查。

---

# 15. 完整配置示例

```yaml
project:
  name: cross_market_full
  seed: 1024
  output_dir: runs

data:
  manifest: data/sample/dataset_manifest.json
  markets: [CN, HK, JP, US]
  base_currency: USD
  lookback: 20
  features: [open, high, low, close, volume, log_return, volatility_20]

split:
  strategy: walk_forward
  train_years: 5
  validation_years: 1
  test_years: 1

environment:
  execution_protocol: close_signal_next_open
  allow_short: false
  initial_cash: 1000000
  max_asset_weight: 0.10
  max_market_weight: 0.40
  cash_floor: 0.05
  transaction_cost_bps: 10
  slippage_bps: 5
  reward: risk_adjusted

rl:
  algorithm: PPO
  total_timesteps: 1000000
  policy: transformer
  device: auto

llm:
  provider: openai_compatible
  base_url_env: LLM_BASE_URL
  api_key_env: LLM_API_KEY
  model: qwen3
  temperature: 0.0

llm_layers:
  research:
    enabled: true
    mode: execute
  risk:
    enabled: true
    mode: enforced
    cadence: weekly
  hierarchical:
    enabled: true
    cadence: monthly
    fusion: constraint

team:
  topology: supervisor_worker
  supervisor: coordinator
  max_rounds: 3
  conflict_policy: most_conservative
  agents:
    - type: research_coordinator
      name: coordinator
      count: 1
      tools: [inspect_dataset, validate_experiment_config, train_rl, tune_rl]
    - type: risk_manager
      name: risk_committee
      count: 3
      tools: [read_risk_report]
    - type: backtest_auditor
      name: audit_committee
      count: 2
      tools: [inspect_execution_log, inspect_split]
```

PSO 调参：

```yaml
study:
  name: ppo_pso
  direction: maximize
  max_trials: 60
  seeds: [11, 22, 33]
  walk_forward_folds: 3

searcher:
  type: pso
  population_size: 12
  inertia: 0.72
  cognitive: 1.49
  social: 1.49

scheduler:
  type: asha
  grace_period: 50000
  reduction_factor: 3

objective:
  type: robust_portfolio_score
  weights:
    sharpe: 1.0
    max_drawdown: -0.5
    turnover: -0.05
    seed_instability: -0.25
```

---

# 16. 测试计划

单元测试：

- Schema、OHLCV、日历、汇率、会计、成本、约束、reward；
- Agent Schema、聚合、搜索器。

属性测试：

- 投影权重满足约束；
- 总资产守恒；
- 成本非负；
- 不可交易资产不成交；
- 固定 seed 可复现；
- 候选不越界。

泄漏测试：

- 归一化器只拟合训练集；
- `t` 状态不含 `t+1`；
- 执行不使用未来收盘；
- HPO 不读测试集；
- LLM 工具不能读取隐藏测试指标。

Agent 测试：

- Mock、Replay、无效 JSON、超时；
- 多 Agent 冲突和仲裁；
- 动态数量；
- 自定义插件；
- 工具权限。

CPU 集成测试：

- 四市场小样本；
- PPO 1000 timesteps；
- 单 Research Agent；
- 3 Risk Agent 委员会；
- PSO 4 粒子 2 代；
- 完整报告。

---

# 17. 分阶段实施

## Phase 0：工程骨架

交付包结构、配置、日志、CI、lint/type/test、CLI 空命令、文档框架。

验收：

```bash
pip install -e .
cmag --help
pytest
ruff check .
mypy src
```

## Phase 1：数据与清单

交付 Schema、Parquet/CSV loader、质量检查、manifest、样例数据。

验收：四市场可加载，问题有报告，哈希可重算。

## Phase 2：环境与会计

交付环境、动作投影、会计、成本、mask、reward、市场规则。

验收：`check_env` 通过；随机动作 1000 step 无 NaN；手工会计案例匹配。

## Phase 3：DRL 与基准

交付 PPO/SAC/TD3、传统基准、训练评估、checkpoint。

验收：三算法可训练，输出 trades/weights/metrics，checkpoint 可复现。

## Phase 4：HPO

交付 SearchSpace、StudyStore、9 个核心搜索器、调度器、报告。

验收：数学函数、小型 RL、resume、Pareto 报告。

## Phase 5：LLM Provider 与工具

交付 Mock/Replay/OpenAI-compatible、工具权限、结构化输出、审计。

验收：离线完整运行，无效输出安全回退，密钥不入日志。

## Phase 6：单/多 Agent Runtime

交付 AgentSpec、TeamSpec、六种拓扑、动态 count、角色注册、聚合裁决。

验收：单 Agent、1+3+2 团队、自定义插件、并行串行、部分失败。

## Phase 7：三层融合

交付 Research、Risk、Hierarchical constraint fusion 和预设模式。

验收：所有预设可运行；关闭 LLM 后无依赖；Risk 不突破硬约束；指令可回放。

## Phase 8：报告和服务

交付 HTML/Markdown、可选 FastAPI、运行浏览和 benchmark 对比。

验收：一条命令生成 SoftwareX 示例所需表图。

## Phase 9：发布准备

交付 PyPI、Docker、README、API 文档、案例、覆盖率、Release/Zenodo、CITATION 和论文素材。

---

# 18. SoftwareX 实验

至少：

1. 环境正确性和市场规则；
2. PPO/SAC/TD3 与传统基准；
3. 跨股票零样本；
4. leave-one-market-out；
5. 市场机制消融；
6. Agent 与 HPO 消融。

Agent 消融：

```text
No LLM
Research only
Risk only
Hierarchical only
Single full-stack Agent
Custom multi-Agent committee
```

HPO：

```text
Default
Random
TPE
CMA-ES
PSO
GA
DE
NSGA-II
```

指标除收益外还包括 Sharpe、Sortino、最大回撤、Calmar、CVaR、换手、成本、跨 seed 方差、运行时间、Agent 任务成功率、配置合法率、泄漏违规率、工具调用准确率、LLM 成本和复现率。

---

# 19. Definition of Done

- [ ] 可安装；
- [ ] CPU quickstart；
- [ ] Gymnasium/SB3 检查通过；
- [ ] PPO/SAC/TD3；
- [ ] 四市场样例；
- [ ] 三层 LLM 全部实现并可独立启停；
- [ ] 单/多 Agent 共用 runtime；
- [ ] 类型和数量可配置；
- [ ] 自定义 Agent 可注册；
- [ ] 至少 9 种核心搜索器；
- [ ] ASHA/HyperBand/PBT 与搜索器分离；
- [ ] HPO 不访问测试集；
- [ ] 数据、配置、LLM 和交易可审计；
- [ ] 泄漏测试通过；
- [ ] 一条命令复现；
- [ ] 文档、示例、许可证和引用完整；
- [ ] 可生成 SoftwareX 论文表图。

---

# 20. Codex 执行规则

1. 按 Phase 顺序，不先堆前端。
2. 每个 Phase 建 issue/checklist。
3. 模块先测试再继续。
4. 核心代码禁用 `eval`。
5. Notebook 不得代替包代码。
6. LLM 不得直接修改账户。
7. 禁止测试集调参。
8. 禁止静默修复异常数据。
9. 禁止直接相加不同币种价格。
10. 所有随机过程可设 seed。
11. 每次运行生成 resolved config 和 run ID。
12. 所有接口有类型和 docstring。
13. 冲突时优先级：无泄漏 > 会计正确 > 可复现 > 风险约束 > 扩展性 > 性能 > 界面。
