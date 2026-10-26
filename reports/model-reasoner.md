# 评测报告

## 汇总对比

| 配置 | 通过/总数 | 成功率 | 平均工具步数 | 平均 token |
| --- | --- | --- | --- | --- |
| skill off / deepseek-reasoner | 0/14 | 0.00% | 4.14 | 501.3 |
| skill on  / deepseek-reasoner | 14/14 | 100.00% | 1.21 | 238.1 |

## 明细 · skill off / deepseek-reasoner

失败归因分布：

| 归因 | 数量 |
| --- | --- |
| unsafe_sql | 12 |
| step_budget_exceeded | 2 |

| 任务 | 结果 | 归因 | gold | got | 步数 |
| --- | --- | --- | --- | --- | --- |
| q01 | FAIL | unsafe_sql | 383 |  | 5 |
| q02 | FAIL | unsafe_sql | 1437 |  | 4 |
| q03 | FAIL | unsafe_sql | S003 |  | 3 |
| q04 | FAIL | unsafe_sql | S003 |  | 3 |
| q05 | FAIL | unsafe_sql | P003 |  | 3 |
| q06 | FAIL | unsafe_sql | 139 |  | 5 |
| q07 | FAIL | unsafe_sql | 3 |  | 3 |
| q08 | FAIL | step_budget_exceeded | 1.0881 |  | 6 |
| q09 | FAIL | unsafe_sql | 1796 |  | 4 |
| q10 | FAIL | unsafe_sql | 248 |  | 4 |
| q11 | FAIL | step_budget_exceeded | 3.2 |  | 6 |
| q12 | FAIL | unsafe_sql | 7 |  | 5 |
| q13 | FAIL | unsafe_sql | 2026-09-04 |  | 3 |
| q14 | FAIL | unsafe_sql | 2815 |  | 4 |

## 明细 · skill on  / deepseek-reasoner

无失败任务。

| 任务 | 结果 | 归因 | gold | got | 步数 |
| --- | --- | --- | --- | --- | --- |
| q01 | PASS | ok | 383 | 城东一店 2026 年 9 月降压片（规格 20mg，P001）的总销量为 383 盒。

答案：383 | 1 |
| q02 | PASS | ok | 1437 | 全部门店 2026 年 9 月降压片 20mg 共售出 1437 盒。

答案：1437 | 1 |
| q03 | PASS | ok | S003 | 2026 年 9 月总销量最高的门店是 S003。
答案：S003 | 1 |
| q04 | PASS | ok | S003 | 2026 年 9 月销售额最高的门店是 S003。

答案：S003 | 1 |
| q05 | PASS | ok | P003 | 2026 年 9 月总销量最低的产品编号为 P003。
答案：P003 | 1 |
| q06 | PASS | ok | 139 | 2026-09-10 城南三店 降压片 40mg 的库存为 139 盒。
答案：139 | 1 |
| q07 | PASS | ok | 3 | 2026-09-10 库存低于 60 盒的门店产品组合共 3 个。
答案：3 | 1 |
| q08 | PASS | ok | 1.0881 | 城东一店 2026 年 9 月降压片 20mg（P001）目标完成率为 1.0881。

答案：1.0881 | 1 |
| q09 | PASS | ok | 1796 | 城东区门店 2026 年 9 月总销量为 1796 盒。
答案：1796 | 3 |
| q10 | PASS | ok | 248 | 城西二店 9 月 1-5 日销量 1070 盒，6-10 日销量 822 盒，前者比后者多 248 盒。
答案：248 | 1 |
| q11 | PASS | ok | 3.2 | 城南三店降压片40mg：9月总销量441盒，日均销量44.1盒，9-10库存139盒，可售约3.2天。
答案：3.2 | 1 |
| q12 | PASS | ok | 7 | 答案：7 | 1 |
| q13 | PASS | ok | 2026-09-04 | 2026 年 9 月全部门店合计销量最高的是 2026-09-04。

答案：2026-09-04 | 1 |
| q14 | PASS | ok | 2815 | 降压片 2026 年 9 月两个规格合计销量：20mg（P001）1437 盒 + 40mg（P002）1378 盒 = 2815 盒。
答案：2815 | 2 |

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
