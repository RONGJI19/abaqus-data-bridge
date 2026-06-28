#!/usr/bin/env python3
"""示例 3: 提取弹簧单元内力.

演示弹簧力 (S11) 和相对位移 (E11) 的提取。
"""

from adb.core.engine import ExtractionEngine
from adb.models.extraction_config import ExtractionConfig

config = ExtractionConfig()
config.inp_file = "tests/fixtures/spring_model.inp"
config.dat_file = "tests/fixtures/spring_model.dat"
config.output_dir = "./output/spring_example"

# 指定弹簧变量
config.variables.spring = ["S11", "E11"]

engine = ExtractionEngine(config)
stats = engine.run()

print(f"Spring elements: {stats['element_count']}")
print(f"Exported files: {stats['exported_files']}")

# 弹簧力值可从 CSV 文件中读取
import csv
import os

for f in os.listdir(config.output_dir):
    if "SPRING" in f or "S11" in f or "SPRING_SET" in f:
        filepath = os.path.join(config.output_dir, f)
        with open(filepath, 'r', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            print(f"\n{f}:")
            for row in reader:
                elem_id = row.get('ENTITY_ID', '?')
                s11 = row.get('S11', '?')
                e11 = row.get('E11', '?')
                print(f"  Element {elem_id}: Force={s11} N, Disp={e11} mm")
