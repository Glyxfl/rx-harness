# 评测报告

## 汇总对比

| 配置 | 通过/总数 | 成功率 | 平均工具步数 | 平均 token |
| --- | --- | --- | --- | --- |
| oracle（链路上限，校准用） | 60/60 | 100.00% | 0.78 | 150.4 |
| heuristic（朴素实现基线） | 9/60 | 15.00% | 1.0 | 165.0 |

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
| q15 | PASS | ok | 1892 | 1892 | 1 |
| q16 | PASS | ok | 85436.0 | 85436.0 | 1 |
| q17 | PASS | ok | 133 | 133 | 1 |
| q18 | PASS | ok | 6989 | 6989 | 1 |
| q19 | PASS | ok | 1573 | 1573 | 1 |
| q20 | PASS | ok | 1892 | 1892 | 1 |
| q21 | PASS | ok | 66339.7 | 66339.7 | 1 |
| q22 | PASS | ok | 1.3117 | 1.3117 | 1 |
| q23 | PASS | ok | 0.7428 | 0.7428 | 1 |
| q24 | PASS | ok | 1.1506 | 1.1506 | 1 |
| q25 | PASS | ok | 城南三店 | 城南三店 | 1 |
| q26 | PASS | ok | 城东一店 | 城东一店 | 1 |
| q27 | PASS | ok | 10 | 10 | 1 |
| q28 | PASS | ok | 450 | 450 | 1 |
| q29 | PASS | ok | 1.3437 | 1.3437 | 1 |
| q30 | PASS | ok | 2 | 2 | 1 |
| q31 | PASS | ok | 1.0775 | 1.0775 | 1 |
| q32 | PASS | ok | 177 | 177 | 1 |
| q33 | PASS | ok | 572.1 | 572.1 | 1 |
| q34 | PASS | ok | 589.8 | 589.8 | 1 |
| q35 | PASS | ok | 0.2506 | 0.2506 | 1 |
| q36 | PASS | ok | 3285 | 3285 | 1 |
| q37 | PASS | ok | 1 | 1 | 1 |
| q38 | PASS | ok | 0.0939 | 0.0939 | 1 |
| q39 | PASS | ok | 609 | 609 | 1 |
| q40 | PASS | ok | 140760.5 | 140760.5 | 1 |
| q41 | PASS | ok | 33.83 | 33.83 | 1 |
| q42 | PASS | ok | 12710 | 12710 | 1 |
| q43 | PASS | ok | 2026-09-03 | 2026-09-03 | 1 |
| q44 | PASS | ok | P002 | P002 | 1 |
| q45 | PASS | ok | 0.23 | 0.23 | 1 |
| q46 | PASS | ok | P004 | P004 | 1 |
| q47 | PASS | ok | 3.0603 | 3.0603 | 1 |
| q48 | PASS | ok |  | 请补充规格相关信息后再查询。 | 0 |
| q49 | PASS | ok |  | 请补充时间相关信息后再查询。 | 0 |
| q50 | PASS | ok |  | 请补充门店相关信息后再查询。 | 0 |
| q51 | PASS | ok |  | 请补充门店相关信息后再查询。 | 0 |
| q52 | PASS | ok |  | 请补充门店相关信息后再查询。 | 0 |
| q53 | PASS | ok |  | 请补充指标相关信息后再查询。 | 0 |
| q54 | PASS | ok |  | 请补充哪两个相关信息后再查询。 | 0 |
| q55 | PASS | ok |  | 请补充定义相关信息后再查询。 | 0 |
| q56 | PASS | ok |  | 请补充哪一周相关信息后再查询。 | 0 |
| q57 | PASS | ok |  | 请补充门店相关信息后再查询。 | 0 |
| q58 | PASS | ok |  | 请补充哪个产品相关信息后再查询。 | 0 |
| q59 | PASS | ok |  | 请补充门店相关信息后再查询。 | 0 |
| q60 | PASS | ok |  | 请补充时间相关信息后再查询。 | 0 |

## 明细 · heuristic（朴素实现基线）

失败归因分布：

| 归因 | 数量 |
| --- | --- |
| answered_wrong | 38 |
| needs_clarification_unmet | 13 |

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
| q15 | PASS | ok | 1892 | 1892 | 1 |
| q16 | FAIL | answered_wrong | 85436.0 | 1437 | 1 |
| q17 | FAIL | answered_wrong | 133 | 3945 | 1 |
| q18 | FAIL | answered_wrong | 6989 | 12710 | 1 |
| q19 | PASS | ok | 1573 | 1573 | 1 |
| q20 | FAIL | answered_wrong | 1892 | 5721 | 1 |
| q21 | FAIL | answered_wrong | 66339.7 | 5721 | 1 |
| q22 | FAIL | answered_wrong | 1.3117 | 1.858 | 1 |
| q23 | FAIL | answered_wrong | 0.7428 | 12 | 1 |
| q24 | FAIL | answered_wrong | 1.1506 | 18.7574 | 1 |
| q25 | FAIL | answered_wrong | 城南三店 | S003 | 1 |
| q26 | FAIL | answered_wrong | 城东一店 | 1573 | 1 |
| q27 | FAIL | answered_wrong | 10 | 12 | 1 |
| q28 | FAIL | answered_wrong | 450 | 1321 | 1 |
| q29 | FAIL | answered_wrong | 1.3437 | 18.7574 | 1 |
| q30 | FAIL | answered_wrong | 2 | 537 | 1 |
| q31 | FAIL | answered_wrong | 1.0775 | 4.5395 | 1 |
| q32 | FAIL | answered_wrong | 177 | 5721 | 1 |
| q33 | FAIL | answered_wrong | 572.1 | 5721 | 1 |
| q34 | FAIL | answered_wrong | 589.8 | 5721 | 1 |
| q35 | FAIL | answered_wrong | 0.2506 | 450 | 1 |
| q36 | FAIL | answered_wrong | 3285 | 12710 | 1 |
| q37 | FAIL | answered_wrong | 1 | 12 | 1 |
| q38 | FAIL | answered_wrong | 0.0939 | 5721 | 1 |
| q39 | FAIL | answered_wrong | 609 | P004 | 1 |
| q40 | FAIL | answered_wrong | 140760.5 | 5721 | 1 |
| q41 | FAIL | answered_wrong | 33.83 | 5721 | 1 |
| q42 | FAIL | answered_wrong | 12710 | 5721 | 1 |
| q43 | FAIL | answered_wrong | 2026-09-03 | 2026-08-26 | 1 |
| q44 | PASS | ok | P002 | P002 | 1 |
| q45 | FAIL | answered_wrong | 0.23 | 465 | 1 |
| q46 | PASS | ok | P004 | P004 | 1 |
| q47 | FAIL | answered_wrong | 3.0603 | 12 | 1 |
| q48 | FAIL | needs_clarification_unmet |  | 3170 | 1 |
| q49 | FAIL | needs_clarification_unmet |  | 3945 | 1 |
| q50 | FAIL | needs_clarification_unmet |  | 1573 | 1 |
| q51 | FAIL | needs_clarification_unmet |  | 18.7574 | 1 |
| q52 | FAIL | needs_clarification_unmet |  | 12710 | 1 |
| q53 | FAIL | needs_clarification_unmet |  | 5721 | 1 |
| q54 | FAIL | needs_clarification_unmet |  | 12710 | 1 |
| q55 | FAIL | needs_clarification_unmet |  | 12710 | 1 |
| q56 | FAIL | needs_clarification_unmet |  | 12710 | 1 |
| q57 | FAIL | needs_clarification_unmet |  | 1573 | 1 |
| q58 | FAIL | needs_clarification_unmet |  | 12710 | 1 |
| q59 | FAIL | needs_clarification_unmet |  | 41.6721 | 1 |
| q60 | FAIL | needs_clarification_unmet |  | 12710 | 1 |

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
