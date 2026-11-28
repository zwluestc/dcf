# 行业研究合成题 · Harbor v1

主包 14 题，扩量包 28 题，合计 42 个原创、可离线评分的行业研究实例，共用 7 种机制。主包每种机制各 2 例，扩量包各 4 例。中文问题、英文合成披露。实例会改变数据与关键结论，例如获批后填平缺口或仍然短缺。两份同机制案例不能视作两个独立题型。

**出题代码**：[批量生成入口](generate.py)负责按种子导出题面、资料、私有答案和 Harbor 目录；[七种行业题型](scenarios.py)定义披露文本、业务口径、问题及其证据。新增题型时，同时更新[公开材料参考解](reference.py)与[错解验收](accept.py)。

从仓库根目录运行，使用 Python 3.12 标准库：

```sh
python3 -B finance_industry/generate.py --seed 736041 --variants 2 --out build/industry-main
python3 -B finance_industry/accept.py build/industry-main
```

[主包 ZIP](../exports/industry-research-harbor-v1.zip) · [扩量包 ZIP](../exports/industry-research-harbor-extra28.zip) · [扩量包 FinanceGym 清单](extra28-questions.jsonl) · [扩量包本地验收](acceptance-newseed.json)。ZIP 内第一层是各个 Harbor 任务，解压后将上层目录传给 `harbor run -p`。扩量包用下方的种子 8301、每类 4 例复现。

[Harbor 任务目录](release/tasks/) · [题目清单 JSONL](release/financegym_questions.jsonl) · [任务来源、文档数及哈希](release/manifest.json) · [验收结果](acceptance.json) · [示例研究简报](example.md)

**已验证。** 主包 14 题的 Harbor Oracle 均得到 1.0，见[容器运行结果](results/harbor-oracle-main.json)。两个包共 42 题均通过本地参考解、对应业务错解、引证、截止日和文档乱序检查；业务错解得分为 0.0–0.6。扩量包未重复运行 Docker。HTTP 最小客户端已通过本机两端口的编码、检索、读取测试。

**模型盲测。** 通过 ENVMUX 调用 `dashscope.deepseek-v4.1-flash-1017`，在公开目录上自主选择要读的原文，再由原评分器离线打分。[严格 JSON 模式](results/deepseek-flash-1017-catalog-v1/REPORT.md)整题满分 25/42，子项值正确 162/216，平均得分 73.24%。有 10 题的首次取文含原生工具标记或额外文本；[兼容模式](results/deepseek-flash-1017-compat-v1/REPORT.md)重放全部原始回复，仅续跑被阻断的调用，不重抽已交卷答案，也不改变最终答案解析或评分。结果为整题满分 32/42，子项值正确 212/216，平均得分 96.48%。只在本合成集单次评测。

| 对齐的能力 | 行业及问题 | 主要失误 |
|---|---|---|
| [Finance Agent Benchmark](https://www.vals.ai/benchmarks/finance_agent)：公司披露、提取和重算 | 晶圆代工：剔除内部调拨，折算面积比出货份额；连锁零售：用关店与开店收入还原可比门店增长 | 混用片径、把全网增长当同店增长 |
| [Samaya FrontierFinance](https://samaya.ai/benchmarks/frontier-finance)：行业、事件、催化剂和情景判断 | 海风：毛授标到已签并网的权益 MW；铜冶炼：加工费重定价到 EBITDA 和契约余量；电池隔膜：行业供需缺口、补贴退出与客户认证两种情景 | 把预留容量当签约、把浮动价冲击套用到固定合同、把完工等同认证 |
| [FinSearchComp](https://arxiv.org/abs/2509.13160)：时点查询和复杂历史调查 | 港口：累计序列拆季与定点勘误；保险并购：还原未受影响股价、监管批准和产权交割时间线 | 忽略勘误、把批准日当成交割日、对未披露事项给出确定日期 |

**与 FinanceHarness 的关系。** 采用[上游 FinanceHarness](https://github.com/google-research/google-research/tree/master/finance_harness) 的检索、取证、计算、引用流程，按 [FinanceGym 的公开契约](https://github.com/google-research/google-research/blob/master/finance_harness/FinanceGym/docs/participate.md) 生成 `task_id / question / cutoff` 记录，提供可用同一最小客户端调用的三个 HTTP 路由，并能将结构化答案转为带引用的 `question / cutoff / report`。合成器、资料、检索器和评分器均为本地原创实现；没有使用官方题库、原始新闻、语义索引、模型权重或官方裁判。本地小语料允许直接读取，使用词项哈希检索；它不测开放互联网搜索、原生 FinanceHarness agent 表现或自由研报文采。没有向官方榜单提交结果。

**运行。** 在含 finance_industry 的工作区根目录运行。环境为 Harbor 0.24.0、Docker 和 `python:3.12.8-slim-bookworm`；首次需已有该镜像或可拉取。每题独立构建，无 pip 依赖、无网络。绝对 jobs 路径可避免 Docker Compose 的相对路径歧义。

```sh
harbor run -p finance_industry/release/tasks -a oracle -n 3 --jobs-dir "$PWD/finance_industry/jobs"
python3 -B finance_industry/accept.py finance_industry/release
```

**接入检索。** 在对应任务的 environment 目录运行 `python3 archive.py serve`，仅绑定本机；也可在题目容器的 /work 启动。服务处理 POST：8888 端口的 `/v1/embeddings` 接收 `{"input":"query"}`；8889 的 `/search` 接收 `query_embedding / k / max_date` 返回 results；`/fetch` 接收 `{"id":"..."}` 返回全文。向量必须由同一实例的本地编码器生成。任务快照中物理剔除截止日后的文件；检索还支持更早日期过滤。fetch 的可见边界为本题固定截止日。也可运行 `python3 archive.py search "customer release" -k 4` 和 `python3 archive.py fetch ID`。

**输出与评分。** Agent 只应看到 instruction.md 和 environment；任务包中的 solution/、tests/、作者种子与 author/ 均不提供给 agent。答案填入 /work/answer.json。每问等权；正确值给 60%，正确值附齐对应的原始材料、无多引再加 40%。错误值没有引用分。数字绝对误差 0.01；枚举、日期、公司名忽略大小写和首尾空格。截止日不符或缺交为零。单题取平均，所有请求字段正确且证据齐才满分。分数仅衡量明确列出的结构化结论与证据归属，不用 LLM 评自由文本。

**如何扩充。** 在新目录生成相同机制的更多案例（Python 3.12）。每个实例独立派生随机数据和文档 ID；正式稿、旧档期、预告与同业材料共同打乱。截止日之后的模拟更正在 author/ 留作不可见性对照。所有数值和判定都是按题面规则得到的派生标签，不是真实预测或投资业绩。

```sh
python3 -B finance_industry/generate.py --seed 8301 --variants 4 --out /tmp/industry-28
python3 -B finance_industry/accept.py /tmp/industry-28
```

新种子只增加实例；要增加研究机制，需同时增加行业资料生成逻辑、独立参考解和有业务含义的错解。当前为开发样题，未划分训练/盲测集。衡量迁移时应按行业机制留出，另生成未公开实例；不要把一对变体拆到训练和测试后宣称题型泛化。

**查看自己的报告。** 从 Harbor trial 的 artifacts/work/answer.json 读取候选答案，下面示例将其转为一条 FinanceGym 格式的 JSONL；加 `--markdown` 可阅读。例中的路径需替换为该 trial 实际产物：

```sh
python3 finance_industry/report.py finance_industry/release/tasks/battery-84e679d5/environment/data /path/to/trial/artifacts/work/answer.json
```

**复算模型成绩。** 两种模式各保存了 42 份逐题记录。下列命令仅用题包及已保存的回答，输出与发布记录相同的评分表：

```sh
python3 -B finance_industry/model_score.py finance_industry/results/deepseek-flash-1017-catalog-v1
python3 -B finance_industry/model_score.py finance_industry/results/deepseek-flash-1017-compat-v1
```

如需重新调用模型，设置自己的 `ENVMUX_BASE_URL`（HTTPS、含 API 前缀）和 `ENVMUX_API_KEY`，用 `python3 finance_industry/model_eval.py --out build/new-run` 写入新的运行目录；未设置密钥时会隐藏输入。发布的 protocol.json 用网关地址的 SHA-256 标识原实验。历史成绩中的模型交互在主机侧执行，Harbor 容器实跑对应上面的 Oracle 记录。
