#!/usr/bin/env python3
"""示例 2: 从接触模型中提取接触力、压力和张开距离.

演示接触结果的提取和统计。
"""

from adb.core.engine import ExtractionEngine
from adb.models.extraction_config import ExtractionConfig

config = ExtractionConfig()
config.inp_file = "tests/fixtures/contact_model.inp"
config.dat_file = "tests/fixtures/contact_model.dat"
config.output_dir = "./output/contact_example"

# 只提取接触变量
config.variables.contact = ["CNORMF", "CPRESS", "COPEN"]

# 执行
engine = ExtractionEngine(config)
stats = engine.run()

print(f"Contact result groups: {stats['result_groups']}")
print(f"Total rows: {stats['total_rows']}")

# 查看每个变量组的统计
for group_name, var_stats in engine.summary.variable_stats.items():
    print(f"\n{group_name}:")
    for var, s in var_stats.items():
        print(f"  {var}: min={s['min']:.4f}, max={s['max']:.4f}, "
              f"mean={s['mean']:.4f}")
