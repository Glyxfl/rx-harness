name: schema
when: 任何需要写 SQL 的任务开始前，表名列名一律以此为准

# 业务库表结构

**不要猜表名和列名，也不要查 information_schema**——这是 SQLite，没有 `information_schema`。
下面是完整结构，直接照此写 SQL。

## sales · 日粒度销量流水
- `date` TEXT，业务日期，格式 `YYYY-MM-DD`
- `store_id` TEXT，门店编号
- `product_id` TEXT，产品编号
- `qty` INTEGER，销量（盒）
- `amount` REAL，销售额（元）

## stores · 门店维度
- `store_id` TEXT
- `name` TEXT，门店名称
- `region` TEXT，所属片区

## products · 产品维度
- `product_id` TEXT
- `name` TEXT，产品名称。同一 `name` 可能有多个 `spec`
- `spec` TEXT，规格

## inventory · 日末库存快照
- `date` TEXT，仅 `2026-09-10` 有数据
- `store_id` TEXT
- `product_id` TEXT
- `qty` INTEGER，库存（盒）

## targets · 月度目标
- `month` TEXT，格式 `YYYY-MM`，库里有 `2026-08` 和 `2026-09` 两个月
- `store_id` TEXT
- `product_id` TEXT
- `target_qty` INTEGER，目标销量（盒）

## 常用 join 键
- `sales.store_id = stores.store_id`
- `sales.product_id = products.product_id`
- `inventory` 与 `sales` 都按「date × store_id × product_id」对齐
- `targets` 与 `sales` 按「month × store_id × product_id」对齐

## 禁止事项
- 不要查 `sqlite_master` 或 `information_schema`，结构已在本文件
- 不要用 MySQL 语法（`DATABASE()`、`information_schema` 等）
