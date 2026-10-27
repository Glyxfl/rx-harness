# 自进化对照 · memory

- 学习者：KnowledgeGatePolicy（单一缺陷：知识缺口）
- dev / holdout：30 / 30
- 重复次数：1
- 接受准则：dev 逐轮结果的中位数严格提升；单次口径只作对照记录
- 可改面：skills
- 初始缺口：列 ['region', 'month', 'target_qty']；字面量 ['20mg']
- 最大代数：8

| 代 | dev（中位数） | dev 逐轮 | holdout | 补丁 | 结果 |
| --- | --- | --- | --- | --- | --- |
| 0 | 13/30 | 13 → 23 | 15/30 | memory-batch · 把 10 道失败题的原题与标准 SQL 追加为示例（记住题目，不是学会规则） | 接受 · 接受：dev 13 → 23（中位数 +10） |
| 1 | 23/30 | 23 | 15/30 | - | 未接受 · 无可执行补丁，停止 |

## 本轮未通过的题目

| 任务 | 归因 |
| --- | --- |
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
| q50 | clarify | 问题条件明显不全（got=12710，与全表求和一致），却直接给了数而没有确认 |
| q52 | clarify | 问题条件明显不全（got=12710，与全表求和一致），却直接给了数而没有确认 |
| q53 | clarify | 问题条件明显不全（got=12710，与全表求和一致），却直接给了数而没有确认 |
| q54 | clarify | 问题条件明显不全（got=12710，与全表求和一致），却直接给了数而没有确认 |
| q55 | clarify | 问题条件明显不全（got=12710，与全表求和一致），却直接给了数而没有确认 |
| q56 | clarify | 问题条件明显不全（got=12710，与全表求和一致），却直接给了数而没有确认 |
| q58 | clarify | 问题条件明显不全（got=12710，与全表求和一致），却直接给了数而没有确认 |

## 泛化差距

- dev：23/30 = 76.7%
- holdout：15/30 = 50.0%
- 差距：26.7 个百分点

差距为正说明补丁含有只在 dev 上成立的部分；差距接近 0 才说明改的是规则而不是记忆。
