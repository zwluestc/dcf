# DCFEval v1 · 财报清洗与存量模型修复

20 道离线 Harbor 任务覆盖 10 种经营模型。每道题的公开资料都包含两家子公司的合成年报、收入更正和债务到期附注，以及经营、预算、同业、资金和估值文件。Agent 要从资料中清洗 FY2025 历史财务数据，预测 FY2026–2030 三张报表，再计算 FCFF 和每股估值。

| 作业方式 | 题数 | 交付要求 |
|---|---:|---|
| 从财报建模 | 14 | 从空工作簿起步，整理两家子公司的披露明细，为每一项历史数值保留来源 |
| 接手并修复模型 | 6 | 在题目提供的 15 张工作表上更新财报、修正公式、采用新假设并重算。工作表结构和未受影响的公式须保留 |

修模型任务为 02、05、09、11、14、18。可以直接对照一个从零建模案例和一个修模型案例。[订阅软件财报建模](DCFEval/dcf-01-saas/instruction.md) · [晶圆代工模型修复](DCFEval/dcf-02-foundry/instruction.md) · [存量工作簿](DCFEval/dcf-02-foundry/environment/data/prior_model.xlsx)

财报清洗需要分清比较期和本期、单位和符号，采用最新签署的更正，区分借款总额和当期到期部分，并抵销内部往来。评分器按来源定位到 28 条清洗记录，用改动原始金额后的重算检验这些记录是否驱动历史报表。存量模型保留经营、营运资本、债务、折旧、税、现金流和折现等计算底稿。每份存量模型含两个未标记的公式错误，以及需要重估的旧假设。详细口径见[评分与验收说明](docs/SCORING_AND_REFERENCE_PIPELINE.md)。

在安装了 Python、openpyxl 和 LibreOffice Calc 的环境从仓库根目录执行：

```sh
python3 dcf_benchmark/build_all.py --seed 2026 --waves 2
python3 dcf_benchmark/accept.py DCFEval results/acceptance.json trajectories/oracle
harbor run -p DCFEval -a oracle
```

Agent 在容器内读取 `/work/data/`，交付 `/work/output.xlsx`。评分依据与参考解分别放在每道题的 `tests/` 和 `solution/`。给独立 Agent 分发材料时，仅使用题面和 `environment/data/`。

本分支的验收结果记录的是参考解、可接受的替代实现和错误对照。此前的模型分数对应旧题集。[v1 题目清单](results/manifest.json) · [逐题验收](results/acceptance.json) · [旧版模型报告](https://github.com/zwluestc/dcf/blob/54179c302783d73b8894f04f8dfbdd79b879d951/README.md)
