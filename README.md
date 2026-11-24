# DCFEval：高难度、完全可验证的从零构建 DCF 估值评测集

`DCFEval` 是一个面向 LLM Agent 的高难度财务建模评测集，接入 [Harbor](https://github.com/laude-institute/harbor) 标准任务格式。全部 10 道题目均为**完全原创的自动化生成案例**（绝不包含外网原题），要求 Agent 在**空白工作簿（不提供模板、公式骨架或已有 DCF 结果）**下，仅凭 7 份原始形态财务材料与业务假设，端到端搭建含动态 Excel 公式的历史重构、未来五年三大报表预测与 FCFF 估值模型。

> 详细评分标准修复推导与参考解双独立路径规范见：[`docs/SCORING_AND_REFERENCE_PIPELINE.md`](docs/SCORING_AND_REFERENCE_PIPELINE.md)。

---

## 一、造题方案与参考解生产流程解读

### 1. 无人工参与、全自动可 Scaling 的双独立路径流水线

全部造题逻辑位于 [`dcf_benchmark/`](dcf_benchmark/)，**100% 纯 Python + 开源 `openpyxl` + LibreOffice**（零人工干预、零 Node.js/私有依赖）。只需更改 `--seed` 即可一键生成全新的独立题库：

```bash
python3 dcf_benchmark/build_all.py --seed 2026 --out DCFEval
```

流水线包含 **4 个确定性阶段** 与 **双独立验证路径**：

1. **多行业参数化场景生成与门禁筛查（[`model.py`](dcf_benchmark/model.py) / [`generate.py`](dcf_benchmark/generate.py)）**
   - 覆盖 10 种差异化经营递推机制（SaaS 订阅流失/扩容、晶圆代工产能与需求上限、装备制造订单递延、仓储库容上限、设备租赁退役与利用率、许可续签与首期签约费、矿业储量耗减、连锁零售新店爬坡、特许权分档与最低保底、售后服务保修抵扣）。
   - 每题独立按种子采样公司营收与三表规模、$R_f$、$\beta$、$\text{ERP}$、$W_d$、$K_d$、税率、永续增长率 $g$、退出倍数、折旧率与稀释股数（彻底消除跨题同质化）。
   - **自动门禁筛查**：要求 $\text{WACC} - g \ge 2.5\%$、正终值与正每股价值、五年现金与净 PP&E 非负，且 4 道含非线性 `MIN/MAX` 约束的题（`foundry / storage / mine / royalty`）**五年内两侧分支均至少触发一次**。
   - **路径 A（纯 Python 数值引擎）**：`model.calculate()` 算出基准与 3 组扰动真值写入 `tests/answers.json`，并硬断言每年资产负债表配平误差 $< 10^{-8}$。
2. **原始形态材料编译（[`raw.py`](dcf_benchmark/raw.py)）**
   - 降维编译为 **7 份原始公开文件** 放入每题 `environment/data/`（无任何 `.xlsx` 模板）：
     - `north_close.csv`（欧元千）与 `south_close.csv`（欧元元）：含 `POSTED` 正式凭证与 `VOID` 作废干扰凭证；银行借款动态拆分为流动债（`2112`）与非流动债（`2710`）；
     - `operations_memo.md`：自然语言经营递推政策与按年驱动参数；
     - `finance_budget.csv`：混合百分数（`pct`）与欧元千的财务预算表；
     - `peer_set.csv`：动态 3 或 5 家可比公司观察 Beta、净 D/E 与法定税率（需用 Hamada 公式逐家去杠杆 → 取中位数 → 再加杠杆）；
     - `treasury_note.md`：以基点（bp）给出的利率参数，以及动态市价与含**价内+价外多批次期权**的股本附注（需用 TSM 过滤价外期权计算稀释股数）；
     - `valuation_policy.md`：折现时点（年中 0.5–4.5 / 年末 1–5）、终值方法（永续增长 / 退出 EBITDA）与折旧政策。
3. **路径 B：仅凭公开材料的纯 Python 动态 Excel 参考解构建（[`reference.py`](dcf_benchmark/reference.py)）**
   - **完全不读取私有 `canonical.json`**，仅通过 `audit_sources.reconstruct()` 解析 `environment/data/` 中的 7 份公开文件，用 `openpyxl` 独立写出纯公式工作簿 `solution/reference.xlsx`（`DCF`、`Statements`、`Inputs`、`Ledger`、`Capital` 五张表），交由第三方 **LibreOffice Calc** 现场重算验证。
4. **公开还原审计（[`audit_sources.py`](dcf_benchmark/audit_sources.py)）与正向 API（[`forward.py`](dcf_benchmark/forward.py)）**
   - `audit_sources.py` 验证 7 份公开文件反向还原与 `answers.json` 在 $10^{-8}$ 内完全一致（10 题共 **7,160 项校验点全过**）。
   - `forward.py` 提供公开 Python CLI/API 直接输出完整三表与估值：
     ```bash
     python3 dcf_benchmark/forward.py DCFEval/dcf-03-orders/solution/canonical.json
     ```

---

### 2. 加固版四维评分标准与动态模型门控（[`grade.py`](dcf_benchmark/grade.py) v2）

在独立无网 Harbor Verifier 容器中调用无头 LibreOffice Calc 现场重算基准及 **3 份动态输入扰动副本**，逐单元格采用 $\max(10^{-6}, 10^{-6}\times|\text{expected}|)$ 容差：

- **递归公式计算链审计**：对 160 个预测/估值单元格检查必须为含单元格引用的有效公式；对单格裸链接（`=Sheet!A1`）递归追踪上游至真正运算公式，同时封堵 `=1.13` 常数伪公式与 `=Helper!A1` 辅助表静态中转作弊。
- **10 项重平衡基础权重**：控制 `3%` + 有效公式 `12%` + 历史 `8%` + 预测三表 `18%` + FCFF `9%` + 估值与资本结构 `14%` + 20 项会计勾稽 `9%` + 价格/回款/折现三组扰动各 `9%`（合计 `27%`）。
- **动态模型门控乘子（杜绝静态硬编码反超动态模型）**：
  $$\text{dynamic\_gate} = 0.25 + 0.75 \times \left(0.6 \cdot \text{formula\_ratio} + 0.4 \cdot \text{shock\_ratio}\right), \qquad \text{reward} = \text{raw\_score} \times \text{dynamic\_gate}$$
  Oracle（`formula_ratio = 1.0`, `shock_ratio = 1.0`）严格得 **`1.0000`**；纯静态硬编码（`frozen`）即使基准全对最高也仅得 **`0.1525`**（彻底修复旧版 `0.6900` 虚高）。

---

## 二、评测集 10 题总览（Seed = 2026）

| 任务 ID | 行业与经营递推考点 | 终值方法 | FCFF 折现 | FY25 收入 (EUR m) | 推导 WACC | 企业价值 EV (EUR m) | 每股内在价值 (EUR) |
|---|---|---|---:|---:|---:|---:|---:|
| [`dcf-01-saas`](DCFEval/dcf-01-saas/instruction.md) | 订阅软件：流失、年中新签与平均计费扩容 | 永续增长 | 年末 | 105.1 | 8.27% | 697.77 | 56.43 |
| [`dcf-02-foundry`](DCFEval/dcf-02-foundry/instruction.md) | 晶圆代工：产能滚动、需求上限与良率（双分支触发） | 退出 EBITDA | 年中 | 215.1 | 8.80% | 878.53 | 63.17 |
| [`dcf-03-orders`](DCFEval/dcf-03-orders/instruction.md) | 装备制造：期初在手订单与新签分期履约递延 | 永续增长 | 年中 | 113.1 | 7.34% | 275.82 | 16.57 |
| [`dcf-04-storage`](DCFEval/dcf-04-storage/instruction.md) | 仓储出租：退租、库容上限与新租半年确认（双分支触发） | 退出 EBITDA | 年末 | 219.5 | 8.04% | 494.02 | 54.51 |
| [`dcf-05-fleet`](DCFEval/dcf-05-fleet/instruction.md) | 设备租赁：年初退役、年中投放与设备利用率 | 永续增长 | 年中 | 193.8 | 8.81% | 711.96 | 55.31 |
| [`dcf-06-license`](DCFEval/dcf-06-license/instruction.md) | 许可合同：续签、持续服务费与一次性签约费 | 退出 EBITDA | 年中 | 140.0 | 9.44% | 493.25 | 39.04 |
| [`dcf-07-mine`](DCFEval/dcf-07-mine/instruction.md) | 矿业：储量发现、开采上限与回收率（双分支触发） | 永续增长 | 年末 | 144.2 | 8.30% | 92.34 | 5.09 |
| [`dcf-08-retail`](DCFEval/dcf-08-retail/instruction.md) | 连锁零售：老店关停与新店首年爬坡系数 | 退出 EBITDA | 年中 | 113.8 | 9.68% | 385.62 | 22.56 |
| [`dcf-09-royalty`](DCFEval/dcf-09-royalty/instruction.md) | 特许权：分档费率、超额折扣与最低保底（双分支触发） | 永续增长 | 年中 | 173.9 | 10.90% | 641.54 | 55.82 |
| [`dcf-10-returns`](DCFEval/dcf-10-returns/instruction.md) | 售后服务：保修到期、新签与期初覆盖量索赔抵扣 | 退出 EBITDA | 年末 | 144.0 | 6.61% | 446.79 | 33.95 |

---

## 三、`harbor run` 复现命令

每题 `environment/Dockerfile` 完全自包含（无需提前手工 `docker build`，10 题共享底层镜像缓存）。

### 1. Oracle 全量验收（10/10 全部 `reward = 1.0`）

```bash
harbor run -p DCFEval -a oracle -n 4 --jobs-dir "$PWD/dcf_benchmark/jobs" --job-name oracle-final
```

### 2. Frontier Model 全量 10 题评测

```bash
# 使用 Harbor 原生 Coding Agent + 最强 Frontier Model
harbor run -p DCFEval -a claude-code -m anthropic/claude-opus-4-6 -n 4 --jobs-dir "$PWD/dcf_benchmark/jobs" --job-name frontier-eval
harbor run -p DCFEval -a codex -m openai/gpt-5 -n 4 --jobs-dir "$PWD/dcf_benchmark/jobs" --job-name frontier-eval

# 或使用仓库自带的标准 OpenAI-Compatible 多轮执行适配器
export OPENAI_API_KEY="your-key"
export OPENAI_BASE_URL="https://api.openai.com/v1"
PYTHONPATH=. harbor run -p DCFEval -a dcf_benchmark.pilot:OpenAICompatAgent -m gpt-5 -n 4 --jobs-dir "$PWD/dcf_benchmark/jobs" --job-name frontier-eval

# 一键输出 Markdown 分数表与逐题首项诊断
python3 dcf_benchmark/report.py dcf_benchmark/jobs/frontier-eval
```

### 3. 无人工扩展全新 Seed 题库与 60 组反例验收

```bash
python3 dcf_benchmark/build_all.py --seed 2027 --out /tmp/DCFEval-2027
python3 dcf_benchmark/accept.py /tmp/DCFEval-2027 /tmp/acceptance-2027.json
```

---

## 四、模型实测分数表与 60 组反例验证

### 1. Harbor Oracle 与 6 类 60 组反例突变验收（[`dcf_benchmark/results/acceptance.json`](dcf_benchmark/results/acceptance.json)）

| 任务 | Harbor Oracle | 纯数值冻结 (`frozen`) | 终值错一年 (`terminal`) | 错纳价外期权 (`itm_filter`) | 常数伪公式 (`fake_formula`) | 静态别名 (`alias_hardcode`) | 缺文件 (`missing`) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `dcf-01-saas` | **1.0000** | 0.1525 | 0.8819 | 0.9422 | 0.9858 | 0.9858 | 0.0000 |
| `dcf-02-foundry` | **1.0000** | 0.1525 | 0.8816 | 0.9412 | 0.9858 | 0.9858 | 0.0000 |
| `dcf-03-orders` | **1.0000** | 0.1525 | 0.8819 | 0.9422 | 0.9858 | 0.9858 | 0.0000 |
| `dcf-04-storage` | **1.0000** | 0.1525 | 0.8816 | 0.9412 | 0.9858 | 0.9858 | 0.0000 |
| `dcf-05-fleet` | **1.0000** | 0.1525 | 0.8819 | 0.9422 | 0.9858 | 0.9858 | 0.0000 |
| `dcf-06-license` | **1.0000** | 0.1525 | 0.8816 | 0.9412 | 0.9858 | 0.9858 | 0.0000 |
| `dcf-07-mine` | **1.0000** | 0.1525 | 0.8816 | 0.9422 | 0.9858 | 0.9858 | 0.0000 |
| `dcf-08-retail` | **1.0000** | 0.1525 | 0.8816 | 0.9412 | 0.9858 | 0.9858 | 0.0000 |
| `dcf-09-royalty` | **1.0000** | 0.1525 | 0.8819 | 0.9422 | 0.9858 | 0.9858 | 0.0000 |
| `dcf-10-returns` | **1.0000** | 0.1525 | 0.8816 | 0.9412 | 0.9858 | 0.9858 | 0.0000 |

### 2. 全量 10 题模型实测分数表（含 v1 vs v2 评分对照）

下表汇总同架构 7 份原始材料版 10 题完整实测（DeepSeek 模型，关闭推理 + 单次异常修复），并展示经新版动态门控评分标准（v2）重算后的得分与排序纠偏：

| 任务 | 交付工作簿 | 动态公式 | 历史 | 预测三表 | FCFF | 估值 | 勾稽 | 三组扰动 | v1 旧分 | **v2 新分** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `dcf-01-saas` | 否 | 0/160 | 0/19 | 0/130 | 0/20 | 0/10 | 0/20 | 0/176 | 0.0000 | **0.0000** |
| `dcf-02-foundry` | 是 | 160/160 | 19/19 | 75/130 | 5/20 | 7/10 | 20/20 | 64/173 | 0.6252 | **0.5101** |
| `dcf-03-orders` | 是 | 160/160 | 18/19 | 25/130 | 0/20 | 4/10 | 15/20 | 0/176 | 0.3680 | **0.2687** |
| `dcf-04-storage` | 是 | **0/160** | 19/19 | 130/130 | 15/20 | 10/10 | 20/20 | **0/173** | ~~0.6650~~ | **0.1469** |
| `dcf-05-fleet` | 否 | 0/160 | 0/19 | 0/130 | 0/20 | 0/10 | 0/20 | 0/176 | 0.0000 | **0.0000** |
| `dcf-06-license` | 是 | 160/160 | 19/19 | 29/130 | 1/20 | 1/10 | 20/20 | 12/173 | 0.3797 | **0.2823** |
| `dcf-07-mine` | 否 | 0/160 | 0/19 | 0/130 | 0/20 | 0/10 | 0/20 | 0/176 | 0.0000 | **0.0000** |
| `dcf-08-retail` | 是 | **0/160** | 19/19 | 25/130 | 0/20 | 5/10 | 20/20 | **0/173** | ~~0.3423~~ | **0.0762** |
| `dcf-09-royalty` | 是 | 160/160 | 19/19 | 35/130 | 0/20 | 5/10 | 20/20 | 0/176 | 0.4292 | **0.3069** |
| `dcf-10-returns` | 是 | 160/160 | 0/19 | 6/130 | 0/20 | 1/10 | 15/20 | 0/173 | 0.1992 | **0.1679** |
| **10 题均值（满分率 0/10）** | **7/10** | — | — | — | — | — | — | — | **0.3009** | **0.1759** |

---

## 五、失败 Case 轨迹级审计与根因归类（是否存在题目歧义？）

逐题审计全部 10 条模型轨迹（`attempt-1/2.py`、`execution-1/2.json` 与 `verifier/details.json`）后，结论非常明确：**10 题中 0 题存在金融口径或数学公式歧义**（尤其是 `dcf-04-storage` 在 Python 侧 100% 精准复现了全部 19 项历史、130 项预测与 10 项估值至 6 位小数，直接反证题面信息完备且零歧义）。全部失分可精确归为 5 类模型自身缺陷：

1. **多表 Excel 坐标/行号管理失控（`dcf-06-license`、`dcf-09-royalty`、`dcf-10-returns`）**：
   - `06` 题 `Inputs` 表参数行号顺延错 1 行（折旧引到永续增长率 `0.024`、利息引到税率 `0.24`、TSM 除以空单元格 `B17` 导致每股价值 `#DIV/0!`），且 `Statements!C33:G33` 错引到空白行 `DCF!F5:F9`；
   - `09` 题在 `DCF` 表中写 `=G32*(1+...)` 和 `=SUM(C33:G33)+B6` 漏写跨表前缀 `Statements!`，直接算出 `EV = 0`；
   - `10` 题把历史实际值写入 `Inputs` 第 28 列（AB 列）却在公式里引用 B 列（把字符串 `"Value"` 和无风险利率当成历史收入与折旧，历史 0/19），同时 `cogs_pct / capex_pct` 重复除以 100。
2. **核心金融估值公式与单位换算错误（`dcf-03-orders`、`dcf-06-license`、`dcf-09-royalty`、`dcf-10-returns`）**：
   - 3 道题（`03 / 09 / 10`）将 `operations_memo.md` 中以 **EUR（元）** 标价的单价漏除以 $10^6$，导致预测收入放大一百万倍；
   - 3 道题（`03 / 06 / 10`）将 CAPM 股权成本 `=Rf + Beta*ERP` 直接当成 WACC，完全漏掉目标债务权重与税后债务成本；
   - `03` 题 FCFF 漏加回非现金折旧 D&A、终值分母把 `WACC - g` 错写成 `Beta - g`；`10` 题退出倍数终值乘的是 EBIT 而非 EBITDA。
3. **经营业务机制理解反转或括号笔误（`dcf-02-foundry`、`dcf-06-license`、`dcf-08-retail`）**：
   - `02` 题折旧公式漏括号写成 `=dep_rate*B19 + 0.5*C18`（应为 `=dep_rate*(B19 + 0.5*C18)`），引发全链路偏移；
   - `06` 题把续签率 `B`（75%–92%）当成流失率写了 `opening*(1-B)+A`（但下一行算 billable 时又写对了 `opening*B`）；
   - `08` 题把关店率 `closure (B) = 0.081294` 当成绝对门店数直接相减 `opening - B`，导致每股估值虚高至 `80.81`（参考值 `57.29`）。
4. **偷懒静态硬编码（`dcf-04-storage`、`dcf-08-retail`、`dcf-09-royalty`）**：
   - `04` 与 `08` 题直接将 Python 算出的死数字写入 Excel（`0/160` 公式，三组扰动全 0）；`09` 题把 WACC/Beta/TSM 在 Python 算死写入 `Inputs` 再用裸链接中转；新版 `grade.py` 的递归计算链审计与 `dynamic_gate` 乘子已将其精准拦截并压低至 `0.1469 / 0.0762`。
5. **原始文本正则解析脆弱 + 单轮修复限制（`dcf-01-saas`、`dcf-05-fleet`、`dcf-07-mine`）**：
   - `01` 题首轮没区分 `north_close.csv`（`amount_EUR_thousands`）与 `south_close.csv`（`amount_EUR_units`）列名报 `KeyError`，次轮切分 `operations_memo.md` 未截断句号后正文；`05 / 07` 题贪婪正则 `[\d.]+` 吞入句末句号触发 `float('0.710581.')` 崩溃；新版 [`raw.py`](dcf_benchmark/raw.py) 已移除句尾句号粘连噪声以进一步聚焦财务建模本身。
