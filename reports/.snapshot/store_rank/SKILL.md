name: store_rank
when: 需要比较门店或产品的排名、找最高或最低时

# 排名口径

- 「销量最高」按 `SUM(qty)`，「销售额最高」按 `SUM(amount)`，两者排序结果可能不同，
  不要混用
- 排名类问题返回编号（`store_id` / `product_id`），不返回中文名称
- 必须 `GROUP BY` 之后再 `ORDER BY` 聚合值；禁止先 `LIMIT` 再聚合
- 并列时取编号最小者，保证结果可复现
- 「哪一天」类问题返回 `YYYY-MM-DD` 格式字符串
