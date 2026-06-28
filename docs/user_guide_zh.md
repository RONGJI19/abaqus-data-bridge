# Abaqus Data Bridge (ADB) 用户指南

> 🔗 从 Abaqus `.inp` / `.dat` 文件中一键提取有限元结果到 CSV — **无需 Abaqus 许可证**

## 1. 简介

### 1.1 什么是 ADB

ADB 是一个纯 Python 命令行工具，通过解析 Abaqus 的文本输入/输出文件（`.inp` 和 `.dat`），将仿真结果提取为结构化的 CSV 表格。

### 1.2 为什么选择 ADB

| 传统方式 | ADB 方式 |
|----------|----------|
| 需要 Abaqus 许可证 + Python API | 纯文本解析，Python 标准库即可 |
| 手工从 DAT 文件复制粘贴 | 一条命令自动提取 |
| 写 `odbAccess` 脚本门槛高 | CLI + YAML 配置，开箱即用 |
| 接触力/弹簧力没有现成工具 | 内置 CNORMF/CPRESS/弹簧 S11 专用解析 |

### 1.3 支持的结果类型

| 类别 | 变量 | 说明 |
|------|------|------|
| 节点位移 | U1, U2, U3, UR1, UR2, UR3 | 平动 + 转动位移 |
| 支反力 | RF1, RF2, RF3 | 节点约束反力 |
| 单元应力 | S11~S33, S12~S23, Mises | 应力分量 + Mises 等效应力 |
| 单元应变 | E11~E33, E12~E23 | 应变分量 |
| 接触面力 | CNORMF, CSHEARF1, CSHEARF2 | 法向 + 切向接触力 |
| 接触压力 | CPRESS, CSHEAR1, CSHEAR2 | 接触应力 |
| 接触位移 | COPEN, CSLIP1, CSLIP2 | 张开距离 + 滑移量 |
| 弹簧内力 | S11 (力), E11 (相对位移) | 弹簧单元输出 |
| 截面力 | SF1~SF3, SM1~SM3 | 截面力 + 弯矩 |

---

## 2. 安装

### 2.1 系统要求

- Python 3.10 或更高版本
- 支持 Windows / macOS / Linux

### 2.2 安装

```bash
pip install abaqus-data-bridge
```

### 2.3 可选依赖

```bash
pip install abaqus-data-bridge[all]  # 包含所有可选功能
```

| 可选包 | 用途 |
|--------|------|
| `tqdm` | 大文件处理时显示进度条 |
| `chardet` | 自动检测 `.dat` 文件编码 (GBK/UTF-8) |
| `openpyxl` | 支持导出 Excel (.xlsx) 格式 |

---

## 3. 快速开始

### 3.1 最简单的用法

```bash
adb extract -i model.inp -d results.dat -o ./output
```

输出：
```
ADB v0.1.0
  INP: model.inp
  DAT: results.dat
  Output: ./output

==================================================
  Extraction Complete
==================================================
  Nodes:       5000
  Elements:    4800
  Node Sets:   15
  Steps:       2
  Result Groups: 8
  Total Rows:  15000
  Files:       8
  Output Dir:  ./output
```

### 3.2 提取特定变量

```bash
# 只提取位移和支反力
adb extract -i model.inp -d results.dat --variables "U,RF"

# 只提取接触力
adb extract -i model.inp -d results.dat --variables "CNORMF,CPRESS"

# 只提取弹簧内力
adb extract -i model.inp -d results.dat --variables "S11"
```

### 3.3 按 Set 筛选

```bash
# 只提取指定节点集
adb extract -i model.inp -d results.dat --nsets "TOP_NODES,BOTTOM_NODES"

# 只提取指定单元集
adb extract -i model.inp -d results.dat --elsets "CONTACT_ELEMENTS"
```

### 3.4 按 Step/Increment 筛选

```bash
# 只提取 Step-2 的最后一帧
adb extract -i model.inp -d results.dat --steps "Step-2" --increments "last"

# 提取所有 Step，但只取第 1、5、10 帧
adb extract -i model.inp -d results.dat --increments "1,5,10"
```

---

## 4. CLI 命令参考

### 4.1 `adb extract` — 主提取命令

```
Usage: adb extract [OPTIONS]

  从 Abaqus 结果中提取数据并导出 CSV。

Options:
  -c, --config PATH       YAML 配置文件路径
  -i, --inp PATH          INP 输入文件路径
  -d, --dat PATH          DAT 结果文件路径
  -o, --output PATH       输出目录 (默认: ./output)
  --nsets TEXT             逗号分隔的节点集名称
  --elsets TEXT            逗号分隔的单元集名称
  --steps TEXT             逗号分隔的 Step 名称
  --increments TEXT        Increment 筛选: last|all|1,3,5
  --variables TEXT         逗号分隔的变量类型
  --encoding TEXT          文件编码 (自动检测)
  --format [csv|tsv]       输出格式 (默认: csv)
  --no-metadata            不包含元数据头部
  --merge                  合并所有结果到一个文件
  --debug                  启用调试日志
  --help                   显示帮助信息
```

### 4.2 `adb inspect` — 查看 DAT 文件内容

```bash
adb inspect results.dat
```

输出示例：
```
Job: contact_model
Analysis: STANDARD
Status: COMPLETED
Steps: 1
  Step-1: 1 increments, 8 tables
CPU Time: 0.28s, Wall Time: 2.0s

--- Detailed Tables ---

[Step-1] Increment 1 (Step Time: 1.000000E-01)
  Table 1: NODE_OUTPUT | Set: CONTACT_SLAVE | Vars: [U1, U2, U3] | Rows: 4
  Table 2: NODE_OUTPUT | Set: CONTACT_MASTER | Vars: [U1, U2, U3] | Rows: 4
  Table 3: CONTACT_OUTPUT | Set: TOP_BOTTOM_SURF | Vars: [CNORMF, CSHEARF1, CSHEARF2] | Rows: 4
  ...
```

### 4.3 `adb list-sets` — 列出 INP 中的 Set

```bash
# 列出所有 Set
adb list-sets model.inp

# 只列节点集
adb list-sets model.inp --type nset

# 只列单元集
adb list-sets model.inp --type elset
```

### 4.4 `adb wizard` — 交互式向导

```bash
adb wizard
```

一步步引导输入文件路径、选择变量、筛选条件，然后自动执行提取。

---

## 5. 配置文件 (YAML)

对于复杂的提取需求，建议使用配置文件模式。

### 5.1 完整配置文件

```yaml
# config.yaml
job:
  name: "bracket_analysis"
  inp_file: "bracket.inp"
  dat_file: "bracket.dat"
  output_dir: "./results"

extraction:
  variables:
    nodal: ["U", "RF"]
    element: ["S"]
    contact: ["CNORMF", "CPRESS", "COPEN"]
    spring: ["S11", "E11"]
    section: ["SF"]

  filters:
    node_sets: ["FIXED_NODES", "LOADED_NODES"]
    element_sets: ["SPRING_SET"]
    steps: ["Step-2"]
    increments: "last"
    bbox: null
    set_pattern: null
    element_types: []

  output:
    format: "csv"
    encoding: "utf-8-sig"
    delimiter: ","
    include_metadata: true
    merge_sets: false
    decimal_places: 6
    include_node_coords: true

  advanced:
    coordinate_system: "global"
    memory_limit_mb: 2048
    detect_incomplete: true
    log_level: "INFO"
```

### 5.2 使用配置文件

```bash
adb extract -c config.yaml
```

命令行参数可以覆盖配置文件中的设置：

```bash
adb extract -c config.yaml --nsets "TOP_NODES" --increments "1,5,10"
```

### 5.3 生成配置模板

```bash
# 模板文件位于安装包的 templates/ 目录
cp $(python -c "import adb; print(adb.__path__[0])")/templates/config_template.yaml ./my_config.yaml
```

---

## 6. CSV 输出格式

### 6.1 文件命名规则

```
{Step}_{Incr}_{SetName}_{VariableType}.csv
```

示例：
```
Step-1_incr1_ALL_NODES_U.csv
Step-1_incr1_CONTACT_SLAVE_RF.csv
Step-1_incr1_TOP_BOTTOM_SURF-BOTTOM_TOP_SURF_MASTER_CNORMF.csv
Step-2_incr5_SPRING_SET_S.csv
```

### 6.2 文件内容格式

```csv
# Abaqus Data Bridge v0.1.0
# Job: simple_truss
# Rows: 5
# Extracted: 2026-06-25 14:30:00
ENTITY_ID,X,Y,Z,U1,U2,U3,RF1,RF2
1,0.0,0.0,0.0,0.000000,0.000000,0.000000,-500.0,-288.68
2,100.0,0.0,0.0,-0.001234,-0.002469,0.000000,0.0,0.0
```

- `#` 开头的行是元数据 (可通过 `--no-metadata` 禁用)
- `ENTITY_ID` 是节点/单元编号
- `X, Y, Z` 是节点坐标 (可通过配置文件关闭)
- 后续列为提取的结果变量

### 6.3 编码选择

| 编码 | 场景 |
|------|------|
| `utf-8-sig` (默认) | Excel 直接打开，推荐 |
| `utf-8` | Python/文本编辑器 |
| `gbk` | 中文 Windows 旧版本 Abaqus 输出 |

---

## 7. 常见场景示例

### 7.1 提取螺栓连接节点的位移

```bash
adb extract \
    -i assembly.inp \
    -d assembly.dat \
    --nsets "BOLT_NODES" \
    --variables "U" \
    --increments "last" \
    -o ./bolt_displacement
```

### 7.2 提取弹簧单元内力并附带坐标

配置文件方式：
```yaml
extraction:
  variables:
    spring: ["S11", "E11"]
  output:
    include_node_coords: true
```

### 7.3 提取接触面结果 (力+压力+开度)

```bash
adb extract \
    -i contact_model.inp \
    -d contact_model.dat \
    --variables "CNORMF,CPRESS,COPEN" \
    -o ./contact_results
```

输出：
```
contact_results/
├── Step-1_incr1_TOP_BOTTOM_SURF-BOTTOM_TOP_SURF_MASTER_CNORMF.csv
├── Step-1_incr1_TOP_BOTTOM_SURF-BOTTOM_TOP_SURF_MASTER_CPRESS.csv
├── Step-1_incr1_TOP_BOTTOM_SURF-BOTTOM_TOP_SURF_SLAVE_CNORMF.csv
└── ...
```

### 7.4 批量处理多个 Job

```bash
# 创建批量脚本
for job in job1 job2 job3; do
    adb extract -i ${job}.inp -d ${job}.dat -o ./all_results/${job}/
done
```

或者创建一个 Python 脚本：

```python
from adb.core.engine import ExtractionEngine
from adb.models.extraction_config import ExtractionConfig

jobs = ["job1", "job2", "job3"]
for job in jobs:
    config = ExtractionConfig()
    config.inp_file = f"{job}.inp"
    config.dat_file = f"{job}.dat"
    config.output_dir = f"./results/{job}"
    engine = ExtractionEngine(config)
    stats = engine.run()
    print(f"{job}: {stats['total_rows']} rows exported")
```

### 7.5 合并所有结果到一个文件

```bash
adb extract -i model.inp -d results.dat --merge -o ./single_file
```

---

## 8. Abaqus 输出设置指南

为了确保 ADB 能够提取到你需要的结果，INP 文件中需要包含相应的 `*PRINT` 请求：

### 8.1 节点输出

```abaqus
*STEP
*STATIC
...
*NODE PRINT, NSET=YOUR_NSET
U,      # 位移
RF,     # 支反力
V,      # 速度 (可选)
A       # 加速度 (可选)
```

### 8.2 单元输出

```abaqus
*EL PRINT, ELSET=YOUR_ELSET
S,      # 应力
E,      # 应变
SF,     # 截面力
SM      # 截面弯矩
```

### 8.3 接触输出

```abaqus
*CONTACT PRINT, MASTER=MASTER_SURF, SLAVE=SLAVE_SURF
CFORCE,   # 接触力 (CNORMF, CSHEARF)
CSTRESS,  # 接触应力 (CPRESS, CSHEAR)
CDISP     # 接触位移 (COPEN, CSLIP)
```

### 8.4 弹簧输出

弹簧单元使用标准的 `*EL PRINT`：
```abaqus
*EL PRINT, ELSET=SPRING_SET
S,      # S11 = 弹簧力 (N)
E       # E11 = 相对位移 (mm)
```

---

## 9. 故障排除

### 9.1 编码问题

**症状**: 中文注释显示乱码，或解析报 `UnicodeDecodeError`

**解决**:
```bash
# 手动指定编码
adb extract -i model.inp -d results.dat --encoding gbk

# 安装 chardet 自动检测
pip install chardet
```

### 9.2 DAT 文件解析不完整

**症状**: `inspect` 显示表格数少于预期

**原因**: 
1. 分析可能未完成 (`THE ANALYSIS HAS BEEN COMPLETED` 不存在)
2. INP 文件中缺少对应的 `*PRINT` 请求

**解决**: 
- 检查 DAT 文件末尾是否有 `THE ANALYSIS HAS BEEN COMPLETED`
- 确认 INP 中有相应的 `*NODE PRINT` / `*EL PRINT` / `*CONTACT PRINT`

### 9.3 大文件内存不足

**症状**: `MemoryError` 或系统卡顿

**解决**:
- ADB 默认使用流式解析，应该不会占用过多内存
- 如果模型 > 100万节点，可以使用 `--merge` 减少导出文件数
- 在配置文件中设置 `advanced.memory_limit_mb` 以启用内存监控

### 9.4 找不到 Set

**症状**: `list-sets` 显示的 Set 与你预期的不符

**原因**:
- NSET/ELSET 可能在 INP 中是大小写敏感的 (取决于 Abaqus 版本)
- 某些 Set 可能是 `INTERNAL` (内部生成的)，生成方式不同

**解决**: 使用 `adb list-sets model.inp` 查看实际存在的 Set 名称

---

## 10. 技术参考

### 10.1 Abaqus 文件类型

| 文件 | 扩展名 | 格式 | 需要许可证? |
|------|--------|------|-------------|
| 输入文件 | `.inp` | 纯文本 | 否 |
| 打印输出 | `.dat` | 纯文本 | 否 |
| 输出数据库 | `.odb` | 二进制 | 是 (需 ABAQUS API) |
| 结果文件 | `.fil` | 二进制/ASCII | 否 (ASCII 模式) |
| 消息文件 | `.msg` | 纯文本 | 否 |
| 状态文件 | `.sta` | 纯文本 | 否 |

### 10.2 Fortran 数值格式

DAT 文件使用 Fortran 科学记数法：
- `1.234E+02` = 123.4
- `0.1234D+02` = 12.34 (双精度)
- `-1.234-02` = -0.01234 (省略 E)
- `**********` = 数值溢出/未定义 (ADB 转为 NaN)

### 10.3 版本兼容性

ADB 目前测试过的 Abaqus 版本：
- Abaqus 6.24 (测试环境)
- 理论上兼容 Abaqus 2016~2025 (DAT 格式变化不大)

如有版本兼容问题，欢迎提 Issue。

---

> **文档版本**: v0.1.0  
> **最后更新**: 2026-06-25
