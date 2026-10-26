# 评测报告

## 汇总对比

| 配置 | 通过/总数 | 成功率 | 平均工具步数 | 平均 token |
| --- | --- | --- | --- | --- |
| oracle（链路上限，校准用） | 14/14 | 100.00% | 1.0 | 168.0 |
| heuristic（朴素实现基线） | 5/14 | 35.71% | 1.0 | 165.0 |

## 明细 · oracle（链路上限，校准用）

无失败任务。

| 任务 | 结果 | 归因 | gold | got | 步数 |
| --- | --- | --- | --- | --- | --- |
| q01 | PASS | ok | 383 | 383 | 1 |
| q02 | PASS | ok | 1437 | 1437 | 1 |
| q03 | PASS | ok | S003 | S003 | 1 |
| q04 | PASS | ok | S003 | S003 | 1 |
| q05 | PASS | ok | P003 | P003 | 1 |
| q06 | PASS | ok | 139 | 139 | 1 |
| q07 | PASS | ok | 3 | 3 | 1 |
| q08 | PASS | ok | 1.0881 | 1.0881 | 1 |
| q09 | PASS | ok | 1796 | 1796 | 1 |
| q10 | PASS | ok | 248 | 248 | 1 |
| q11 | PASS | ok | 3.2 | 3.2 | 1 |
| q12 | PASS | ok | 7 | 7 | 1 |
| q13 | PASS | ok | 2026-09-04 | 2026-09-04 | 1 |
| q14 | PASS | ok | 2815 | 2815 | 1 |

## 明细 · heuristic（朴素实现基线）

失败归因分布：

| 归因 | 数量 |
| --- | --- |
| answered_wrong | 9 |

| 任务 | 结果 | 归因 | gold | got | 步数 |
| --- | --- | --- | --- | --- | --- |
| q01 | PASS | ok | 383 | 383 | 1 |
| q02 | PASS | ok | 1437 | 1437 | 1 |
| q03 | PASS | ok | S003 | S003 | 1 |
| q04 | PASS | ok | S003 | S003 | 1 |
| q05 | PASS | ok | P003 | P003 | 1 |
| q06 | FAIL | answered_wrong | 139 | 119 | 1 |
| q07 | FAIL | answered_wrong | 3 | 1573 | 1 |
| q08 | FAIL | answered_wrong | 1.0881 | 1.363 | 1 |
| q09 | FAIL | answered_wrong | 1796 | 5721 | 1 |
| q10 | FAIL | answered_wrong | 248 | 1892 | 1 |
| q11 | FAIL | answered_wrong | 3.2 | 119 | 1 |
| q12 | FAIL | answered_wrong | 7 | 12 | 1 |
| q13 | FAIL | answered_wrong | 2026-09-04 | 2026-08-26 | 1 |
| q14 | FAIL | answered_wrong | 2815 | 5721 | 1 |

## 评测器变异测试

对同一道题注入 6 类已知故障，检查评测器能否归因到对应标签。
归因准确率：**6/6**

| 注入故障 | 期望归因 | 实际归因 | 命中 |
| --- | --- | --- | --- |
| wrong_filter | answered_wrong | answered_wrong | Y |
| wrong_aggregation | answered_wrong | answered_wrong | Y |
| wrong_table | answered_wrong | answered_wrong | Y |
| unsafe_sql | unsafe_sql | unsafe_sql | Y |
| no_answer | no_answer | no_answer | Y |
| step_budget | step_budget_exceeded | step_budget_exceeded | Y |
