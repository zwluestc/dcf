# DeepSeek Flash 1017 行业研究盲测

网关指定模型：`dashscope.deepseek-v4.1-flash-1017`。42 个合成实例、7 种研究机制；完成可评分 42 题，基础设施失败 0 题。每题新对话、一次交卷、无评分反馈。只给公开目录，模型可按 ID 分批取全文（最多 3 轮），未提供答案、搜索排序提示、Python 或联网浏览。使用已发布 Harbor grader 离线评分，没有在 Harbor 容器内调用模型。

整题满分 25/42 (59.5%)；全题所有值正确 31/42 (73.8%)；子项值正确 162/216 (75.0%)；证据集合完全匹配 156/216 (72.2%)；值和证据同时正确 156/216 (72.2%)；逐题等权平均分 73.24%。

| 分组 | 题数 | 整题满分 | 全部值正确 | 子项值正确 | 值与证据均对 | 平均分 |
|---|---:|---:|---:|---:|---:|---:|
| main | 14 | 8 | 11 | 57/72 | 54/72 | 77.0% |
| extra | 28 | 17 | 20 | 105/144 | 102/144 | 71.4% |
| battery | 6 | 3 | 6 | 36/36 | 33/36 | 96.7% |
| foundry | 6 | 5 | 5 | 25/30 | 25/30 | 83.3% |
| insurer | 6 | 4 | 6 | 30/30 | 28/30 | 97.3% |
| port | 6 | 5 | 5 | 25/30 | 25/30 | 83.3% |
| retail | 6 | 3 | 3 | 16/30 | 16/30 | 53.3% |
| smelter | 6 | 3 | 3 | 15/30 | 15/30 | 50.0% |
| wind | 6 | 2 | 3 | 15/30 | 14/30 | 48.7% |

## 失分项

| 题型 | 子项 | 值正确 | 引用正确 | 次数 |
|---|---|---|---|---:|
| battery | catalyst_readthrough | True | False | 3 |
| retail | reported_pct | False | False | 3 |
| retail | comparable_pct | False | False | 3 |
| retail | gap_pp | False | False | 3 |
| retail | readthrough | False | False | 3 |
| smelter | exposed_tonnes | False | False | 3 |
| smelter | loss_usd_m | False | False | 3 |
| smelter | post_cny_m | False | False | 3 |
| smelter | headroom_cny_m | False | False | 3 |
| smelter | test | False | False | 3 |
| wind | awarded_gross | False | False | 3 |
| wind | bankable_equity | False | False | 3 |
| wind | watch_equity | False | False | 3 |
| wind | conversion_pct | False | False | 3 |
| wind | next_catalyst | False | False | 3 |
| insurer | elapsed_days | True | False | 2 |
| retail | perimeter_net | False | False | 2 |
| wind | next_catalyst | True | False | 1 |
| foundry | a_external | False | False | 1 |
| foundry | b_external | False | False | 1 |
| foundry | a_share_pct | False | False | 1 |
| foundry | leader | False | False | 1 |
| foundry | physical_count_bias | False | False | 1 |
| port | q2_local | False | False | 1 |
| port | q3_local | False | False | 1 |
| port | peak_quarter | False | False | 1 |
| port | peak_local | False | False | 1 |
| port | annual_local | False | False | 1 |

模型回复数 76；网关报告 token 数：{'prompt_tokens': 195549, 'completion_tokens': 63973}。未测多个采样种子。7 组题均为同机制变体，不能把分数外推为官方榜单成绩。

[逐题打分及失分时的原始答案对照](scores.json) · [请求设置](protocol.json)
