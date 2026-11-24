# 解题轨迹归档目录（`trajectories/`）

本目录用于归档并推送 `DCFEval` 全部 20 道题目的完整解题轨迹与验证明细，按 **模型 → 题目** 两级结构组织，确保所有实测得分与失败 Case 分析均**完全可追溯、可复核**。

## 目录结构规范

```text
trajectories/
├── README.md                                 # 本说明文件
├── oracle/                                   # Oracle 20/20 全量验收轨迹（已归档）
│   ├── dcf-01-saas/
│   │   ├── agent/trajectory.json             # 执行元信息（轮次、耗时、Token、交付状态）
│   │   └── verifier/
│   │       ├── details.json                  # grade.py v3.0 完整逐项评分与抽样明细
│   │       └── reward.txt                    # 最终得分（1.0）
│   └── ... (dcf-02-foundry ~ dcf-20-returns)
└── <model_slug>/                             # 各 Frontier Model 完整解题轨迹（评测完成后归档推送）
    └── dcf-XX-<slug>/
        ├── agent/
        │   ├── trajectory.json               # 汇总：turns / total_elapsed_sec / input&output&total_tokens / delivered / last_error
        │   ├── attempt-1.py ... attempt-k.py # 每轮完整生成的建模代码
        │   ├── execution-1.json ...          # 每轮容器执行退出码与 stdout/stderr
        │   └── usage-1.json ...              # 每轮 API 耗时、Token 消耗与 finish_reason
        └── verifier/
            ├── details.json                  # 无头 LibreOffice 现场重算后的四支柱与门控明细
            └── reward.txt                    # 最终 Reward
```

## 一键脱敏导入与聚合命令

每次使用 `harbor run` 完成一个或多个 Frontier Model 的 20 题评测后，直接运行以下命令即可完成**路径/密钥脱敏归档**、**多模型对比表生成（平均得分、平均时间、平均 Token、平均调用轮次）**与**逐模型失败 Case 归纳**：

```bash
python3 dcf_benchmark/report.py \
  --models \
    oracle=trajectories/oracle \
    claude-opus=dcf_benchmark/jobs/eval-claude-opus \
    gpt-5=dcf_benchmark/jobs/eval-gpt5 \
  --export-trajectories trajectories \
  --json-out results/leaderboard.json
```

> **脱敏保障**：`report.py` 在导出至 `trajectories/` 时会自动剔除本机绝对路径（`/Users/...`、`/home/...`）及任意 `Bearer` 凭证片段，确保轨迹可直接安全推送至公开仓库。
