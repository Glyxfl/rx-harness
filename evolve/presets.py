"""初始缺口预设。

挑这三列 + 一处规格说明，而不是随机删，原因是它们各对应一种**不同类型的知识**：

- `region`      —— 列存在但值域没写（"城东" 是不是 "城东区"）
- `month`       —— 多表关联时的时间粒度口径
- `target_qty`  —— 分母字段，缺了就算不出完成率
- `20mg/40mg`   —— 同一品名下的规格区分，属于业务规则而非结构

四种缺口需要四种不同的补法，一次补不完——这样"第几代修好了什么"才有信息量。
"""
from __future__ import annotations

DEFAULT_DROP_COLUMNS = ("region", "month", "target_qty")
DEFAULT_DROP_LITERALS = ("20mg",)
