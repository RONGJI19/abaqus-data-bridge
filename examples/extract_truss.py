#!/usr/bin/env python3
"""示例 1: 从简单桁架模型中提取位移和应力.

演示基本的 API 用法。
"""

from adb.core.engine import ExtractionEngine
from adb.models.extraction_config import ExtractionConfig

# 创建配置
config = ExtractionConfig()
config.inp_file = "tests/fixtures/simple_truss.inp"
config.dat_file = "tests/fixtures/simple_truss.dat"
config.output_dir = "./output/truss_example"

# 筛选: 只提取 SUPPORT 节点集
config.filters.node_sets = ["SUPPORT"]

# 执行提取
engine = ExtractionEngine(config)
stats = engine.run()

# 查看统计
print(f"Nodes: {stats['node_count']}")
print(f"Elements: {stats['element_count']}")
print(f"Exported: {stats['exported_files']} files")
print(f"Total rows: {stats['total_rows']}")

# 打印摘要报告
print(engine.summary.to_text())
