# CrossMarketAgentGym 后续阶段执行报告（Phase 10–17）

## 0. 文档目的

本报告承接 Phase 0–9。后续阶段的目标是把“功能完成的软件”转化为可冻结、可复现、可引用、可投稿和可维护的科研软件成果。

总体顺序：

```text
Phase 10  发布候选版本冻结
Phase 11  第三方独立复现
Phase 12  正式科研实验
Phase 13  基准结果冻结
Phase 14  正式发布 v1.0.0
Phase 15  SoftwareX 论文与补充材料
Phase 16  投稿门禁与正式提交
Phase 17  审稿回复、维护与后续版本
```

每个阶段必须输出：目标、输入条件、任务、文件改动、脚本、测试、交付物、验收标准、阻断条件、修复策略和阶段完成报告。

---

# Phase 10：发布候选版本冻结

## 10.1 目标

形成不可随意变更的候选版本：

```text
v1.0.0-rc1
```

冻结公共 API、配置 Schema、数据 Manifest、运行目录、Agent 消息格式、HPO Study 格式和审计日志格式。本阶段不运行最终论文实验，也不继续无边界增加功能。

## 10.2 输入条件

必须满足：

- Phase 0–9 Definition of Done 全部通过；
- CPU quickstart 可运行；
- PPO、SAC、TD3 可训练和评估；
- 三层 LLM Agent 可独立启停；
- 多 Agent Runtime 可运行；
- HPO 可运行和恢复；
- 关键泄漏测试通过；
- 主要 CLI 可用。

任一条件不满足时，退回对应开发阶段。

## 10.3 执行任务

### API 与版本策略

建立：

```text
docs/api_stability.md
docs/versioning_policy.md
docs/deprecation_policy.md
release/api_inventory.csv
```

将接口标记为：

- stable；
- provisional；
- experimental；
- internal。

### 依赖冻结

生成：

```text
uv.lock
constraints-cpu.txt
constraints-gpu.txt
environment-cpu.yml
environment-gpu.yml
```

要求：

- CPU 环境不依赖 CUDA；
- GPU、Ray、服务端和云 LLM Provider 使用 optional extras；
- 核心依赖不得使用未固定版本的 Git URL；
- 兼容性矩阵记录 Python、PyTorch、Gymnasium、SB3、Optuna 和 Ray 组合。

### 代码清理

清除：

- 调试 print；
- 临时路径；
- 未使用依赖；
- 废弃配置；
- 未实现 TODO；
- 示例密钥；
- 静默异常处理；
- 只在作者机器有效的路径。

TODO 分为 release blocker 和 future enhancement，release blocker 必须清零。

### 文档补齐

至少包括：

```text
README.md
docs/installation.md
docs/quickstart.md
docs/data_schema.md
docs/environment.md
docs/market_rules.md
docs/rl_training.md
docs/llm_agents.md
docs/multi_agent.md
docs/tuning.md
docs/reproducibility.md
docs/troubleshooting.md
docs/security.md
docs/faq.md
```

### 构建脚本

```text
scripts/build_release.sh
scripts/verify_release.sh
scripts/create_clean_env_test.sh
```

验证：

```bash
python -m build
pip install dist/*.whl
cmag --help
cmag quickstart
pytest
```

## 10.4 新增发布文件

```text
release/
├── rc1_checklist.md
├── api_inventory.csv
├── known_issues.md
├── compatibility_matrix.md
└── release_notes_v1.0.0-rc1.md
```

## 10.5 测试

- 全量单元测试；
- 属性测试；
- 泄漏测试；
- CPU 集成测试；
- Wheel 安装测试；
- Docker 构建测试；
- CLI smoke test；
- 文档命令测试；
- LLM Mock/Replay；
- HPO resume。

## 10.6 验收标准

- [ ] 所有稳定 API 有文档；
- [ ] release blocker 清零；
- [ ] 新环境可安装 wheel；
- [ ] CPU 和 Docker quickstart 成功；
- [ ] 配置 Schema 已冻结；
- [ ] 锁文件和兼容矩阵完整；
- [ ] 测试全部通过；
- [ ] 可创建 `v1.0.0-rc1`；
- [ ] Release notes 与 known issues 完整。

## 10.7 阻断条件

不得进入 Phase 11 的情况：

- 核心 API 仍频繁改变；
- CPU 安装失败；
- Quickstart 依赖私有数据；
- 测试存在随机失败；
- 运行目录缺少审计信息；
- 文档必须依靠作者口头解释。

---

# Phase 11：第三方独立复现与可用性测试

## 11.1 目标

验证非作者能否只依赖公开文档完成安装、数据检查、环境验证、DRL 训练、Agent 运行、HPO 和报告生成。

## 11.2 测试人员

至少三类：

1. 熟悉强化学习但不熟悉金融规则；
2. 熟悉金融数据但不熟悉 Agent；
3. 熟悉 Python 但不熟悉项目。

建议至少 3 人，最好 5 人。测试者不得让作者远程代操作，只允许提交 Issue 和填写记录。

## 11.3 复现任务

```bash
git clone <repository>
pip install -e ".[dev]"
cmag data validate --config configs/data/sample.yaml
cmag env check --config configs/env/sample_cross_market.yaml
cmag train --config configs/train/ppo_quickstart.yaml
cmag agent run --config configs/agents/research_single_mock.yaml
cmag agent run --config configs/agents/risk_committee_mock.yaml
cmag tune --config configs/tune/ppo_pso_quickstart.yaml
cmag report --run-id <RUN_ID>
cmag reproduce --run-id <RUN_ID>
```

## 11.4 记录指标

- 操作系统与 Python；
- 安装耗时；
- 首次成功时间；
- 失败次数；
- 文档查找时间；
- 询问作者次数；
- 错误信息可理解性；
- 任务完成率；
- 复现指标误差；
- Issue 数量和严重度；
- 主观可用性评分。

目录：

```text
reproducibility_tests/
├── protocol.md
├── participant_template.md
├── participant_01.md
├── participant_02.md
├── participant_03.md
├── issue_summary.csv
└── reproducibility_report.md
```

## 11.5 问题分级

- P0：无法安装、会计错误、泄漏、结果严重不一致；
- P1：核心命令、Agent 或 HPO 不可运行；
- P2：文档关键步骤或错误信息问题；
- P3：排版和次要体验。

进入 Phase 12 前：

- P0 = 0；
- P1 = 0；
- P2 已修复或有明确接受说明。

## 11.6 自动化

```text
scripts/repro_test_cpu.sh
scripts/repro_test_docker.sh
scripts/compare_reproduced_run.py
```

比较：

- 配置哈希；
- 数据哈希；
- 关键指标；
- 交易记录；
- Agent Replay；
- HPO 状态。

## 11.7 验收标准

- [ ] 所有测试者完成安装；
- [ ] CPU quickstart 成功率 100%；
- [ ] 核心任务完成率不低于 90%；
- [ ] 不需要作者直接操作；
- [ ] 同一 seed 位于允许误差；
- [ ] P0/P1 清零；
- [ ] 文档按反馈更新；
- [ ] 发布 `v1.0.0-rc2`。

---

# Phase 12：正式科研实验

## 12.1 目标

使用冻结协议运行可进入 SoftwareX 论文的正式实验。开发期 smoke test、调试结果和单 seed 最佳结果不得作为正式结果。

## 12.2 实验协议冻结

正式运行前冻结：

- 数据版本和股票池；
- 训练、验证、测试时间；
- walk-forward 划分；
- 成本、滑点、汇率和市场规则；
- DRL 搜索空间；
- Agent 模型、Prompt 和工具权限；
- seed；
- 计算预算；
- 指标和统计方法。

生成：

```text
experiments/protocol_v1.yaml
experiments/protocol_v1.sha256
```

修改协议必须创建新版本，禁止覆盖。

## 12.3 数据隔离

必须保证：

- 训练集训练；
- 验证集早停和 HPO；
- 测试集只做锁定配置的最终评估；
- 归一化器仅在训练集拟合；
- 无未来股票池、汇率和复权信息；
- 不随机打乱时间序列。

## 12.4 实验组 A：环境正确性

用人工可手算数据验证：

- 成本；
- 滑点；
- T+1；
- 停牌；
- 涨跌停；
- 最小交易单位；
- 休市；
- 汇率；
- 权重投影；
- 现金与持仓；
- 组合净值。

输出：

```text
results/environment_validation/
```

## 12.5 实验组 B：策略兼容性

至少：

```text
Cash
Buy and Hold
Equal Weight
Risk Parity
Mean-Variance
PPO
SAC
TD3
```

所有策略使用相同数据、成本、执行协议、再平衡频率、风险约束和指标。

## 12.6 实验组 C：跨市场泛化

```text
CN + HK + JP → US
CN + HK + US → JP
CN + JP + US → HK
HK + JP + US → CN
```

同时比较：

- 单市场训练；
- 多市场联合训练；
- 未见股票；
- leave-one-market-out；
- 市场规则开关。

## 12.7 实验组 D：市场机制消融

依次关闭：

- 成本；
- 滑点；
- T+1；
- 涨跌停；
- 停牌；
- 汇率变化；
- 异步日历；
- 换手限制；
- 风险投影。

报告收益、Sharpe、回撤、换手、交易次数、无效订单和运行时间变化。

## 12.8 实验组 E：LLM Agent 消融

```text
No LLM
Research only
Risk only
Hierarchical only
Research + Risk
Full-stack single Agent
Custom multi-Agent committee
```

评价：

- 任务成功率；
- 配置合法率；
- 工具调用准确率；
- 泄漏违规率；
- 风险指令合法率；
- 冲突解决率；
- 报告完整率；
- Token/API 成本；
- 额外耗时；
- 重复运行一致性；
- 投资组合指标。

必须固定 Prompt、温度、轮数和权限，保存完整 Replay。

## 12.9 实验组 F：HPO

核心对比：

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

可补充 SA、GWO、WOA。

公平预算：

- 相同 trial 数；
- 相同训练步数；
- 相同 seed 和 fold；
- 相同早停；
- 相同搜索空间；
- 相同硬件预算。

报告验证得分、最终测试得分、收敛、成本、稳定性、Pareto front 和调参过拟合。

## 12.10 统计分析

核心实验至少 5 个 seed。报告：

- mean；
- std；
- median；
- 95% CI；
- best；
- worst；
- fold-level result。

按需要使用配对/非参数检验、多重比较校正和效应量。不能只报告 p 值或最佳 seed。

## 12.11 运行审计

每个 run 保存：

- run ID；
- protocol hash；
- dataset hash；
- commit；
- seed；
- 环境和硬件；
- wall time；
- 状态；
- failure reason。

失败 run 不得删除。

## 12.12 验收标准

- [ ] 协议已冻结；
- [ ] 正式结果不来自开发 run；
- [ ] 至少 5 seed；
- [ ] HPO 与测试集隔离；
- [ ] 所有结果可追溯；
- [ ] 失败运行保留；
- [ ] 表图可自动生成；
- [ ] Agent Replay 完整；
- [ ] 结果经独立复核。

---

# Phase 13：基准结果冻结

## 13.1 目标

冻结正式结果为：

```text
benchmark-v1
```

论文中的每个数字、表格和图必须映射到该基准。

## 13.2 目录

```text
benchmarks/v1/
├── README.md
├── protocol.yaml
├── protocol.sha256
├── dataset_manifest.json
├── dataset_manifest.sha256
├── code_commit.txt
├── symbols/
├── splits/
├── seeds.json
├── runs.csv
├── metrics/
├── trades/
├── weights/
├── agent_logs/
├── tuning_logs/
├── tables/
├── figures/
├── statistical_tests/
├── checksums.json
└── benchmark_report.html
```

## 13.3 自动命令

```bash
cmag benchmark build --protocol experiments/protocol_v1.yaml
cmag benchmark verify --benchmark benchmarks/v1
cmag paper export-tables --benchmark benchmarks/v1
cmag paper export-figures --benchmark benchmarks/v1
```

## 13.4 表格

自动输出 CSV、LaTeX、Markdown、HTML：

- 数据集统计；
- 环境验证；
- 策略比较；
- 跨市场泛化；
- 市场机制消融；
- Agent 消融；
- HPO；
- 运行成本；
- 第三方复现。

## 13.5 图形

至少：

- 架构图数据；
- 训练曲线；
- 净值和回撤；
- 市场敞口；
- 换手；
- Agent 工具调用；
- HPO 收敛；
- Pareto front；
- 跨市场矩阵；
- 置信区间。

禁止手工修改后失去来源。

## 13.6 校验

`cmag benchmark verify` 检查：

- 文件和哈希；
- 配置与 run 对应；
- 表图来源；
- 无测试集调参；
- Agent 日志完整；
- 失败有解释。

## 13.7 验收标准

- [ ] benchmark-v1 只读；
- [ ] 所有论文数字可追溯；
- [ ] 表图自动生成；
- [ ] 哈希通过；
- [ ] 至少一名非作者复核；
- [ ] benchmark report 完整。


---

# Phase 14：正式发布 v1.0.0

## 14.1 目标

发布可公开安装、引用和归档的软件稳定版本：

```text
v1.0.0
```

该版本必须与 `benchmark-v1`、论文和数据 Manifest 一致。

## 14.2 发布内容

- 代码托管平台 Release；
- source archive；
- wheel；
- sdist；
- PyPI 包；
- Docker 镜像；
- 版本化文档站；
- 公开样例数据；
- 轻量样例 checkpoint；
- benchmark-v1；
- CITATION.cff；
- Release notes；
- Known limitations；
- Security policy；
- 长期归档 DOI。

## 14.3 版本映射

固定记录：

```text
Software version: v1.0.0
Benchmark version: benchmark-v1
Data manifest version: dataset-manifest-v1
Paper experiment protocol: protocol-v1
```

新增：

```text
release/release_manifest_v1.0.0.json
release/release_manifest_v1.0.0.sha256
```

## 14.4 PyPI 验证

在全新 CPU 环境：

```bash
pip install crossmarket-agentgym==1.0.0
cmag --version
cmag quickstart
```

必须成功。

## 14.5 Docker 验证

```bash
docker pull <registry>/<image>:1.0.0
docker run --rm <registry>/<image>:1.0.0 cmag quickstart
```

必须成功。

## 14.6 文档站

版本：

```text
latest
stable
v1.0.0
```

必须包含：

- 安装；
- Quickstart；
- Python API；
- CLI；
- 数据 Schema；
- 多市场环境；
- DRL；
- 三层 LLM Agent；
- 多 Agent Runtime；
- HPO；
- Benchmark；
- 复现；
- FAQ；
- 引用方式；
- 已知限制。

## 14.7 DOI 归档

归档：

- 源代码；
- 文档；
- 示例；
- Manifest；
- Benchmark 元数据；
- Release notes；
- CITATION；
- 许可证。

禁止把无再分发权限的原始金融数据错误归档。对于受限数据，只归档获取脚本、Schema、股票清单、日期范围、哈希和公开小样本。

## 14.8 发布自动化

新增：

```text
.github/workflows/release.yml
scripts/publish_pypi.sh
scripts/publish_docker.sh
scripts/create_archive.sh
scripts/verify_public_release.sh
```

发布流程必须支持 dry-run。

## 14.9 验收标准

- [ ] PyPI 安装成功；
- [ ] Docker 运行成功；
- [ ] DOI 可访问；
- [ ] 文档站可访问；
- [ ] Release 与 benchmark 对应；
- [ ] 软件和数据许可证清楚；
- [ ] CITATION 正确；
- [ ] 安全与限制声明完整；
- [ ] `cmag release verify --version 1.0.0` 通过。

## 14.10 阻断条件

- Release 与论文实验 commit 不一致；
- PyPI 或 Docker 不能独立运行；
- DOI 中包含无权公开的数据；
- 文档命令失效；
- Benchmark 哈希不一致。

---

# Phase 15：SoftwareX 论文与补充材料

## 15.1 目标

基于 `v1.0.0` 和 `benchmark-v1` 完成 SoftwareX 论文、补充材料、Highlights、Graphical Abstract、Cover Letter 和复现说明。

## 15.2 题目建议

首选：

```text
CrossMarketAgentGym: An auditable agent-orchestrated framework for deep reinforcement learning across heterogeneous equity markets
```

备选：

```text
CrossMarketAgentGym: A market-aware Gymnasium framework for reproducible multi-market portfolio reinforcement learning
```

## 15.3 论文主线

论文应突出：

- 多市场日度环境；
- 交易日历、币种和市场规则；
- 无信息泄漏执行协议；
- DRL 统一接口；
- 三层 LLM Agent；
- 单/多 Agent 可配置 Runtime；
- HPO 的搜索器—调度器分离；
- 审计、Replay 和复现；
- 支持跨市场泛化等新研究问题。

不要将主线写成“某个 PPO 或多 Agent 策略收益最高”。

## 15.4 章节结构

### 1. Motivation and significance

回答：

- 为什么多市场金融 RL 难复现；
- 现有工具在哪些方面不足；
- 为什么时间语义、市场规则、Agent 审计和 HPO 公平性重要；
- 软件支持哪些新研究。

### 2. Software description

建议小节：

```text
2.1 Overall architecture
2.2 Data harmonization and market calendars
2.3 Gymnasium portfolio environment
2.4 DRL trainers and baseline strategies
2.5 Three-layer LLM Agent system
2.6 Configurable single/multi-Agent runtime
2.7 Hyperparameter optimization
2.8 Audit and reproducibility
```

### 3. Illustrative examples

三个主案例：

1. 使用 PPO 训练多市场组合；
2. 单 Research Agent 与自定义多 Agent 风险委员会；
3. 使用 PSO/TPE 调优并导出报告。

### 4. Impact

必须说明软件如何：

- 支持跨市场和未见股票研究；
- 降低重复数据工程；
- 使市场规则消融标准化；
- 比较单 Agent 与多 Agent；
- 比较 LLM 三层融合；
- 公平比较 HPO；
- 提高实验审计与复现。

### 5. Conclusions

总结能力、限制和后续路线。不得声称具有实盘收益保证。

## 15.5 推荐图表

图：

1. 系统总架构；
2. 日度执行时序与多市场掩码；
3. 三层 LLM Agent；
4. 单/多 Agent Runtime；
5. HPO 搜索与调度；
6. 代表性实验结果。

表：

1. 与现有工具功能比较；
2. 多市场数据与规则；
3. 策略兼容性及跨市场结果；
4. Agent 消融；
5. HPO 对比；
6. 复现、运行时间和成本。

## 15.6 补充材料

```text
supplementary/
├── S1_full_configuration.md
├── S2_dataset_protocol.md
├── S3_market_rules.md
├── S4_agent_prompts.md
├── S5_hpo_spaces.md
├── S6_all_results.csv
├── S7_statistical_tests.md
├── S8_reproduction_guide.md
└── S9_known_limitations.md
```

涉及 Prompt 时，公开：

- 系统 Prompt；
- 角色模板；
- JSON Schema；
- 工具说明；
- 模型参数；
- 隐私或密钥必须删除。

## 15.7 可用性声明

准备：

- Code availability；
- Data availability；
- Software availability；
- CRediT；
- Funding；
- Conflict of interest；
- AI-assisted use declaration；
- Not investment advice；
- Third-party licenses。

## 15.8 自动化

新增：

```bash
cmag paper verify --paper paper/softwarex/
cmag paper export-tables --benchmark benchmarks/v1
cmag paper export-figures --benchmark benchmarks/v1
cmag paper build-supplement --benchmark benchmarks/v1
```

所有数值引用均生成来源映射：

```text
paper/result_provenance.csv
```

字段：

```text
paper_location
table_or_figure
metric
value
run_id
source_file
protocol_hash
dataset_hash
commit
```

## 15.9 验收标准

- [ ] 全文数字来自 benchmark-v1；
- [ ] 命令真实可运行；
- [ ] 软件版本和 DOI 明确；
- [ ] 图表自动生成；
- [ ] 结果来源映射完整；
- [ ] 不夸大投资能力；
- [ ] 数据限制明确；
- [ ] LLM 非确定性和失败回退明确；
- [ ] 市场模拟限制明确；
- [ ] 补充材料完整；
- [ ] 内部语言与技术审查通过。

---

# Phase 16：投稿前门禁与正式提交

## 16.1 目标

建立自动化和人工联合门禁，阻止软件、实验或论文版本不一致的投稿。

## 16.2 软件门禁

- [ ] 全新 CPU 环境安装；
- [ ] Docker 安装；
- [ ] PyPI 稳定版本；
- [ ] 文档所有链接；
- [ ] DOI；
- [ ] Git Release；
- [ ] CPU quickstart；
- [ ] 测试通过；
- [ ] 许可证；
- [ ] 样例数据；
- [ ] Agent Replay；
- [ ] HPO resume；
- [ ] 安全扫描；
- [ ] 密钥扫描。

## 16.3 科研门禁

- [ ] 未使用测试集调参；
- [ ] 未随机打乱金融时间；
- [ ] 策略使用同一成本和执行规则；
- [ ] 汇率处理正确；
- [ ] 市场规则配置一致；
- [ ] 股票池、生存和退市偏差已说明；
- [ ] 至少 5 seed；
- [ ] 置信区间；
- [ ] 失败 run 保留；
- [ ] Agent 失败和回退报告；
- [ ] LLM 成本和版本记录；
- [ ] HPO 公平预算；
- [ ] 所有结果可追溯；
- [ ] Benchmark 校验通过。

## 16.4 论文门禁

- [ ] 摘要和结论不夸大；
- [ ] 每项贡献有代码或实验支撑；
- [ ] 表图可追溯；
- [ ] 引用正确；
- [ ] 仓库和 DOI 可访问；
- [ ] 使用最新投稿模板；
- [ ] 软件元数据表完整；
- [ ] Highlights；
- [ ] Graphical Abstract；
- [ ] Cover Letter；
- [ ] Supplementary；
- [ ] 声明完整；
- [ ] 文件命名符合系统要求。

## 16.5 自动脚本

```text
scripts/submission_gate.sh
```

内部运行：

```bash
pytest
ruff check .
mypy src
python -m build
cmag benchmark verify --benchmark benchmarks/v1
cmag release verify --version 1.0.0
cmag paper verify --paper paper/softwarex/
```

输出：

```text
submission_gate_report.html
submission_gate_report.json
```

JSON 中每个门禁项包含：

```text
id
category
status
evidence
checked_at
tool_version
failure_reason
```

## 16.6 内部预审

至少安排：

1. 软件工程预审；
2. 金融实验预审；
3. 强化学习预审；
4. LLM Agent/HPO 预审；
5. 英文与期刊格式预审。

模板：

```text
reviews/internal_review_template.md
```

严重问题必须清零。

## 16.7 提交 Manifest

```text
submission/
├── submission_manifest.json
├── paper_version.txt
├── software_version.txt
├── benchmark_version.txt
├── dataset_manifest_version.txt
├── doi.txt
├── submitted_files.sha256
└── submission_gate_report.pdf
```

Manifest 必须列出所有提交文件、哈希、版本和生成时间。

## 16.8 正式提交后

记录：

- Manuscript number；
- Submission date；
- Submitted revision；
- 对应代码版本；
- 对应 DOI；
- 提交文件哈希。

不得在提交后覆盖对应 Release 或 benchmark。

## 16.9 验收标准

- [ ] 门禁全部通过；
- [ ] 内部预审重大问题清零；
- [ ] 文件哈希固定；
- [ ] 论文、软件、Benchmark、数据版本一致；
- [ ] 正式提交完成；
- [ ] 提交记录归档。

---

# Phase 17：审稿回复、维护与后续版本

## 17.1 目标

保证投稿后软件持续可用，并建立审稿意见、补充实验和版本维护的可追踪流程。

## 17.2 分支策略

```text
main
release/1.x
develop
paper/revision-1
paper/revision-2
```

论文修订不得直接破坏 `v1.0.0`。

## 17.3 Issue 标签

```text
bug
documentation
reproducibility
data
environment
rl
agent
hpo
paper-review
security
enhancement
breaking-change
```

优先级：

- P0：安全、会计、泄漏、无法安装；
- P1：核心功能；
- P2：文档和兼容；
- P3：增强。

## 17.4 审稿追踪

```text
paper/revisions/
├── reviewer_1_comments.md
├── reviewer_2_comments.md
├── editor_comments.md
├── response_matrix.csv
├── revision_plan.md
└── response_letter.md
```

每条意见记录：

- 原始意见；
- 分类；
- 是否需要代码；
- 是否需要新实验；
- 负责人；
- 状态；
- commit；
- run ID；
- 论文位置；
- 回复文字。

## 17.5 新实验规则

需要新增实验时：

1. 新建 `protocol_revision_N.yaml`；
2. 不修改 benchmark-v1；
3. 新建 `benchmark-v1-revision-N`；
4. 保存新增运行；
5. 自动更新表图；
6. 记录与原实验差异；
7. 不删除或覆盖原结果。

## 17.6 版本发布规则

Patch：

```text
v1.0.1
v1.0.2
```

用于 Bug、文档和非破坏性兼容修复。

Minor：

```text
v1.1.0
```

用于新 Agent、新搜索器、Hierarchical conditioning、新市场适配器。

Major：

```text
v2.0.0
```

用于事件驱动架构、重大 Schema 或破坏性 API。

## 17.7 后续路线

### v1.1

- Hierarchical conditioning；
- 更多 Agent 聚合；
- 分布式 HPO；
- 文档和示例增强。

### v1.2

- UTC 事件驱动环境；
- 更精确跨时区开收盘；
- 动态股票池；
- 退市处理。

### v1.3

- 新闻、财报、公告；
- 多模态 Agent；
- 文本检索和事件信号。

### v2.0

- 实时模拟；
- Paper trading；
- 隔离的券商接口；
- 更完整订单生命周期。

## 17.8 长期维护指标

每季度统计：

- 安装成功率；
- Issue 首次响应时间；
- Bug 关闭时间；
- 下载量；
- 外部贡献；
- 引用；
- 文档访问；
- 第三方复现；
- 支持平台；
- 依赖安全问题。

## 17.9 验收标准

- [ ] 审稿意见可逐项追踪；
- [ ] 新实验协议化；
- [ ] 原 benchmark 不被覆盖；
- [ ] Patch 有回归测试；
- [ ] 文档同步；
- [ ] Release notes 完整；
- [ ] 路线图和维护指标明确。

---

# 18. 总体验收矩阵

| 阶段 | 核心产物 | 进入下一阶段条件 |
|---|---|---|
| 10 | v1.0.0-rc1 | API、依赖、文档和构建冻结 |
| 11 | v1.0.0-rc2 | 第三方可复现，P0/P1 清零 |
| 12 | 正式实验结果 | 协议冻结，运行可追溯 |
| 13 | benchmark-v1 | 所有表图可生成和校验 |
| 14 | v1.0.0 + DOI | PyPI、Docker、文档和归档可用 |
| 15 | 论文与补充材料 | 全文与 benchmark 一致 |
| 16 | 投稿包 | 软件、科研、论文门禁通过 |
| 17 | 修订与维护体系 | 版本和审稿意见可追踪 |

---

# 19. Codex 阶段完成报告模板

```markdown
# Phase XX Completion Report

## 1. Summary
## 2. Input Preconditions
## 3. Completed Tasks
## 4. Added Files
## 5. Modified Files
## 6. Design Decisions
## 7. Tests Executed
## 8. Test Results
## 9. Artifacts Produced
## 10. Known Issues
## 11. Deviations from Specification
## 12. Exit Criteria
## 13. Next Phase Readiness
```

Codex 不得只回复“已完成”。

---

# 20. 执行优先级

出现冲突时：

1. 防止信息泄漏；
2. 会计与交易规则正确；
3. 可复现；
4. 数据和版本可追溯；
5. 第三方可安装；
6. 风险约束；
7. API 稳定；
8. 实验公平；
9. 性能；
10. 界面。

---

# 21. Phase 10–17 最终完成定义

全部完成后，项目必须具备：

- 稳定版本；
- 可引用 DOI；
- PyPI 与 Docker；
- 第三方复现报告；
- 正式 benchmark；
- 自动表图；
- SoftwareX 投稿材料；
- 投稿门禁报告；
- 审稿修订机制；
- 长期维护路线。

只有达到这些条件，CrossMarketAgentGym 才从工程项目转化为可发表、可引用、可复现、可维护的科研软件成果。
