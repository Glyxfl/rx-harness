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
- `store_id` TEXT
- `product_id` TEXT

## 常用 join 键
- `sales.store_id = stores.store_id`
- `sales.product_id = products.product_id`
- `inventory` 与 `sales` 都按「date × store_id × product_id」对齐
- `targets` 与 `sales` 按「month × store_id × product_id」对齐

## 禁止事项
- 不要查 `sqlite_master` 或 `information_schema`，结构已在本文件
- 不要用 MySQL 语法（`DATABASE()`、`information_schema` 等）

## 字段清单（由库结构自动重建）

### _meta_inventory
- `note` TEXT

### _meta_products
- `note` TEXT

### _meta_sales
- `note` TEXT

### _meta_stores
- `note` TEXT

### _meta_targets
- `note` TEXT

### inventory
- `date` TEXT
- `store_id` TEXT
- `product_id` TEXT
- `qty` INTEGER

### products
- `product_id` TEXT
- `name` TEXT
- `spec` TEXT

### sales
- `date` TEXT
- `store_id` TEXT
- `product_id` TEXT
- `qty` INTEGER
- `amount` REAL

### stores
- `store_id` TEXT
- `name` TEXT
- `region` TEXT

### targets
- `month` TEXT
- `store_id` TEXT
- `product_id` TEXT
- `target_qty` INTEGER

以上为库中实际存在的全部列；清单外的列名一律不存在，不要臆造。

## 字段清单（由库结构自动重建）

### _meta_inventory
- `note` TEXT

### _meta_products
- `note` TEXT

### _meta_sales
- `note` TEXT

### _meta_stores
- `note` TEXT

### _meta_targets
- `note` TEXT

### inventory
- `date` TEXT
- `store_id` TEXT
- `product_id` TEXT
- `qty` INTEGER

### products
- `product_id` TEXT
- `name` TEXT
- `spec` TEXT

### sales
- `date` TEXT
- `store_id` TEXT
- `product_id` TEXT
- `qty` INTEGER
- `amount` REAL

### stores
- `store_id` TEXT
- `name` TEXT
- `region` TEXT

### targets
- `month` TEXT
- `store_id` TEXT
- `product_id` TEXT
- `target_qty` INTEGER

以上为库中实际存在的全部列；清单外的列名一律不存在，不要臆造。

## 值域（中文名与编号的对应）

- `城东一店` 对应 `store_id='S001'`
- `城西二店` 对应 `store_id='S002'`
- `城南三店` 对应 `store_id='S003'`
- `stores.region` 的取值为：`城东` / `城西` / `城南`
  **不含「区」字后缀**，`region='城东'` 不是 `region='城东区'`

## 值域（中文名与编号的对应）

- `城东一店` 对应 `store_id='S001'`
- `城西二店` 对应 `store_id='S002'`
- `城南三店` 对应 `store_id='S003'`
- `stores.region` 的取值为：`城东` / `城西` / `城南`
  **不含「区」字后缀**，`region='城东'` 不是 `region='城东区'`
