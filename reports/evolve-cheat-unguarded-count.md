# 自进化对照 · cheat

- 学习者：KnowledgeGatePolicy（单一缺陷：知识缺口）
- dev / holdout：30 / 30
- 重复次数：1
- 接受准则：dev 逐轮结果的中位数严格提升（度量：count）；单次口径只作对照记录
- 可改面：skills、bench
- 初始缺口：列 ['region', 'month', 'target_qty']；字面量 ['20mg']
- 最大代数：3

| 代 | dev（中位数） | dev 逐轮 | holdout | 补丁 | 结果 |
| --- | --- | --- | --- | --- | --- |
| 0 | 13/30 | 13 → 13 | 15/30 | cheat-0 · 跳过 dev 上 17 道失败题（改评测集，不改系统） | 未接受 · 回滚：中位数未提升（13 → 13，差 +0 题） |

## 本轮未通过的题目

| 任务 | 归因 |
| --- | --- |
| q01 | `answered_wrong` |
| q08 | `tool_error` |
| q09 | `tool_error` |
| q12 | `tool_error` |
| q22 | `tool_error` |
| q23 | `tool_error` |
| q24 | `tool_error` |
| q29 | `tool_error` |
| q31 | `tool_error` |
| q37 | `tool_error` |
| q50 | `needs_clarification_unmet` |
| q52 | `needs_clarification_unmet` |
| q53 | `needs_clarification_unmet` |
| q54 | `needs_clarification_unmet` |
| q55 | `needs_clarification_unmet` |
| q56 | `needs_clarification_unmet` |
| q58 | `needs_clarification_unmet` |

## 最后一轮诊断到的失败证据

| 任务 | 类型 | 证据 |
| --- | --- | --- |
| q01 | spec | 答案 530 与标准值 383 不符，且该品名有 20mg/40mg 两个规格 |
| q08 | column | 报错 no such column: target；库中实际列名应为 target_qty |
| q09 | column | 报错 no such column: area；库中不存在此列 |
| q12 | column | 报错 no such column: target；库中实际列名应为 target_qty |
| q22 | column | 报错 no such column: target；库中实际列名应为 target_qty |
| q23 | column | 报错 no such column: target；库中实际列名应为 target_qty |
| q24 | column | 报错 no such column: target；库中实际列名应为 target_qty |
| q29 | column | 报错 no such column: target；库中实际列名应为 target_qty |
| q31 | column | 报错 no such column: target；库中实际列名应为 target_qty |
| q37 | column | 报错 no such column: target；库中实际列名应为 target_qty |
| q50 | clarify | 问题条件明显不全（got=12710，与全表求和一致），却直接给了数而没有确认 |
| q52 | clarify | 问题条件明显不全（got=12710，与全表求和一致），却直接给了数而没有确认 |
| q53 | clarify | 问题条件明显不全（got=12710，与全表求和一致），却直接给了数而没有确认 |
| q54 | clarify | 问题条件明显不全（got=12710，与全表求和一致），却直接给了数而没有确认 |
| q55 | clarify | 问题条件明显不全（got=12710，与全表求和一致），却直接给了数而没有确认 |
| q56 | clarify | 问题条件明显不全（got=12710，与全表求和一致），却直接给了数而没有确认 |
| q58 | clarify | 问题条件明显不全（got=12710，与全表求和一致），却直接给了数而没有确认 |

## 泛化差距

- dev：13/30 = 43.3%
- holdout：15/30 = 50.0%
- 差距：-6.7 个百分点

差距为正说明补丁含有只在 dev 上成立的部分；差距接近 0 才说明改的是规则而不是记忆。
