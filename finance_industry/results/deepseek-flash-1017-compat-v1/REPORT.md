# DeepSeek Flash 1017 行业研究盲测

网关指定模型：`dashscope.deepseek-v4.1-flash-1017`。42 个合成实例、7 种研究机制；完成可评分 42 题，基础设施失败 0 题。每题新对话、一次交卷、无评分反馈。只给公开目录，模型可按 ID 分批取全文（最多 3 轮），未提供答案、搜索排序提示、Python 或联网浏览。使用已发布 Harbor grader 离线评分，没有在 Harbor 容器内调用模型。

整题满分 32/42 (76.2%)；全题所有值正确 41/42 (97.6%)；子项值正确 212/216 (98.1%)；证据集合完全匹配 203/216 (94.0%)；值和证据同时正确 203/216 (94.0%)；逐题等权平均分 96.48%。

| 分组 | 题数 | 整题满分 | 全部值正确 | 子项值正确 | 值与证据均对 | 平均分 |
|---|---:|---:|---:|---:|---:|---:|
| main | 14 | 10 | 14 | 72/72 | 68/72 | 97.8% |
| extra | 28 | 22 | 27 | 140/144 | 135/144 | 95.8% |
| battery | 6 | 3 | 6 | 36/36 | 33/36 | 96.7% |
| foundry | 6 | 6 | 6 | 30/30 | 30/30 | 100.0% |
| insurer | 6 | 4 | 6 | 30/30 | 28/30 | 97.3% |
| port | 6 | 5 | 6 | 30/30 | 29/30 | 98.7% |
| retail | 6 | 5 | 5 | 26/30 | 26/30 | 86.7% |
| smelter | 6 | 6 | 6 | 30/30 | 30/30 | 100.0% |
| wind | 6 | 3 | 6 | 30/30 | 27/30 | 96.0% |

## 失分项

| 题型 | 子项 | 值正确 | 引用正确 | 次数 |
|---|---|---|---|---:|
| battery | catalyst_readthrough | True | False | 3 |
| wind | next_catalyst | True | False | 3 |
| insurer | elapsed_days | True | False | 2 |
| port | annual_local | True | False | 1 |
| retail | reported_pct | False | False | 1 |
| retail | comparable_pct | False | False | 1 |
| retail | gap_pp | False | False | 1 |
| retail | readthrough | False | False | 1 |

模型回复数 90；网关报告 token 数：{'prompt_tokens': 245598, 'completion_tokens': 99952}。未测多个采样种子。7 组题均为同机制变体，不能把分数外推为官方榜单成绩。

[逐题打分及失分时的原始答案对照](scores.json) · [请求设置](protocol.json)
